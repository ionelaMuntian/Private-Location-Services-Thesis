import base64
import tempfile
from pathlib import Path
from time import time
from typing import Any
from uuid import uuid4

def _next_power_of_2(n: int) -> int:
    if n <= 1:
        return 1
    return 1 << (n - 1).bit_length()

from fastapi import HTTPException

import openfhe
from openfhe import (
    BINARY,
    DeserializeCiphertext,
    DeserializeCryptoContext,
    SerializeToFile,
)

_DeserializePublicKey = getattr(openfhe, "DeserializePublicKey", None)

_FLEXIBLEAUTO = getattr(openfhe, "FLEXIBLEAUTO",
                        getattr(openfhe, "ScalingTechnique", openfhe).FLEXIBLEAUTO)

from ....core.metrics import StepTimer
from ..repository import PoiRepository

_KEY_TTL_SECONDS = 60 * 60
_KEY_STORE: dict[str, dict] = {}

# Per-key_id deserialized crypto context cache.
# OpenFHE stores eval-mult keys in a global in-process registry.
# Re-deserializing the same context on every request causes registry collisions
# when multiple N values coexist.  Caching the cc object avoids this: keys are
# loaded once and remain registered for the lifetime of the key_id.
_CC_CACHE: dict[str, Any] = {}

repository = PoiRepository()

# Scales squared-metre distances into the FHEW-optimal range [0, ~0.5].
# Cluj city-scale max dist² ≈ 1e8 m²; 5e-9 maps that to ~0.5, safely below
# the 1.0 padding mask.  Larger scale = more FHEW precision bits used.
_DIST_SCALE = 5e-9

# Fixed batch size matching the client runtime (N_SS=128).
_BATCH_SIZE = 128

# SS parameters — must match the client's openfhe_ss_runtime.py exactly.
_N_SLOTS = 128
_N_VALUES = 128


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _b64decode(data: str) -> bytes:
    return base64.b64decode(data.encode("utf-8"))


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def _write_b64_to_temp(payload_b64: str) -> str:
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(_b64decode(payload_b64))
        return tmp.name


def _serialize_to_b64(obj: Any) -> str:
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        path = tmp.name
    try:
        if not SerializeToFile(path, obj, BINARY):
            raise RuntimeError("OpenFHE SS: failed to serialize object.")
        return _b64encode(Path(path).read_bytes())
    finally:
        Path(path).unlink(missing_ok=True)


def _cleanup_expired_keys() -> None:
    now = time()
    expired = [
        kid for kid, entry in _KEY_STORE.items()
        if now - float(entry["created_at"]) > _KEY_TTL_SECONDS
    ]
    for kid in expired:
        _KEY_STORE.pop(kid, None)
        _CC_CACHE.pop(kid, None)


# ---------------------------------------------------------------------------
# Key upload — single round
# ---------------------------------------------------------------------------

def execute_openfhe_ss_upload_keys(
    crypto_context_b64: str,
    public_key_b64: str,
    eval_mult_keys_b64: str,
    n_candidates: int,
    eval_automorphism_keys_b64: str = "",
    fhew_context_b64: str = "",
) -> dict:
    """
    Deserialise the client's CKKS CryptoContext and load eval mult keys.
    The server only performs CKKS distance computation — all scheme switching
    (EvalMinSchemeSwitching) runs on the client side.
    """
    _cleanup_expired_keys()

    key_id = str(uuid4())
    print(f"[OpenFHE SS] Key upload: key_id={key_id[:8]}...", flush=True)

    cc = _load_crypto_context(crypto_context_b64)
    _load_eval_mult_keys(cc, eval_mult_keys_b64)

    _KEY_STORE[key_id] = {
        "public_key_b64": public_key_b64,
        "n_candidates": n_candidates,
        "created_at": time(),
    }
    _CC_CACHE[key_id] = cc

    print(f"[OpenFHE SS] Keys loaded, ready for distance computation.", flush=True)
    return {
        "key_id": key_id,
        "expires_in_seconds": _KEY_TTL_SECONDS,
        "status": "ready",
    }


# ---------------------------------------------------------------------------
# Deserialization helpers
# ---------------------------------------------------------------------------

def _load_keys(key_id: str) -> dict:
    _cleanup_expired_keys()
    entry = _KEY_STORE.get(key_id)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail="OpenFHE SS key_id not found or expired. Re-upload keys.",
        )
    return entry


def _load_crypto_context(context_b64: str):
    path = _write_b64_to_temp(context_b64)
    try:
        cc, ok = DeserializeCryptoContext(path, BINARY)
        if not ok:
            raise RuntimeError("OpenFHE SS: failed to deserialize CryptoContext.")
        return cc
    finally:
        Path(path).unlink(missing_ok=True)


def _load_eval_mult_keys(cc, emk_b64: str) -> None:
    path = _write_b64_to_temp(emk_b64)
    try:
        try:
            if not cc.DeserializeEvalMultKey(path, BINARY):
                raise RuntimeError("OpenFHE SS: failed to deserialize EvalMult keys.")
        except RuntimeError as exc:
            if "there is a key vector for the given keyTag" not in str(exc):
                raise
    finally:
        Path(path).unlink(missing_ok=True)


def _load_eval_automorphism_keys(cc, eak_b64: str) -> None:
    if not eak_b64:
        return
    path = _write_b64_to_temp(eak_b64)
    try:
        try:
            if not cc.DeserializeEvalAutomorphismKey(path, BINARY):
                raise RuntimeError("OpenFHE SS: failed to deserialize EvalAutomorphism keys.")
        except RuntimeError as exc:
            if "key" in str(exc).lower() and "already" in str(exc).lower():
                pass  # duplicate key, safe to ignore
            else:
                raise
    finally:
        Path(path).unlink(missing_ok=True)


def _load_ciphertext(ct_b64: str):
    path = _write_b64_to_temp(ct_b64)
    try:
        ct, ok = DeserializeCiphertext(path, BINARY)
        if not ok:
            raise RuntimeError("OpenFHE SS: failed to deserialize ciphertext.")
        return ct
    finally:
        Path(path).unlink(missing_ok=True)


def _load_public_key(pk_b64: str):
    if _DeserializePublicKey is None:
        raise RuntimeError("OpenFHE SS: DeserializePublicKey not found in openfhe module.")
    path = _write_b64_to_temp(pk_b64)
    try:
        pk, ok = _DeserializePublicKey(path, BINARY)
        if not ok:
            raise RuntimeError("OpenFHE SS: failed to deserialize public key.")
        return pk
    finally:
        Path(path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Evaluation: vectorised CKKS distances + server-side argmin via EvalMinSchemeSwitching
# ---------------------------------------------------------------------------

def execute_openfhe_ss_evaluate(
    key_id: str,
    encrypted_qy: str,
    encrypted_qx: str,
    category: str,
    n_candidates: int,
) -> dict:
    """
    1. Load cached CKKS context.
    2. Fetch POIs from DB.
    3. Compute vectorised scaled squared distances in CKKS.
    4. Return encrypted distance ciphertext to the client for local EvalMinSchemeSwitching.
    """
    total_timer = StepTimer()

    entry = _load_keys(key_id)
    n = entry["n_candidates"]

    if n_candidates != n:
        raise HTTPException(
            status_code=422,
            detail=(
                f"n_candidates={n_candidates} does not match the uploaded key setup "
                f"(n={n}). Re-upload keys."
            ),
        )

    # --- Fetch candidates -----------------------------------------------
    candidate_timer = StepTimer()
    rows = repository.get_all_by_category(category=category, limit=n)
    actual_n = len(rows)
    if actual_n == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No POIs found for category '{category}'.",
        )

    candidates = [
        {
            "id": r["id"],
            "name": r["name"],
            "category": r["category"],
            "latitude": float(r["latitude"]),
            "longitude": float(r["longitude"]),
            "lat_m": float(r["lat_m"]),
            "lon_m": float(r["lon_m"]),
        }
        for r in rows
    ]

    py_vals = [float(c["lat_m"]) for c in candidates]
    px_vals = [float(c["lon_m"]) for c in candidates]

    while len(py_vals) < _BATCH_SIZE:
        py_vals.append(0.0)
        px_vals.append(0.0)
    py_vals = py_vals[:_BATCH_SIZE]
    px_vals = px_vals[:_BATCH_SIZE]

    candidate_ms = candidate_timer.elapsed_ms()

    cc = _CC_CACHE.get(key_id)
    if cc is None:
        raise HTTPException(status_code=404, detail="OpenFHE SS: CC not in cache.")

    ct_qy = _load_ciphertext(encrypted_qy)
    ct_qx = _load_ciphertext(encrypted_qx)

    # --- Compute vectorised scaled dist² ---------------------------------
    compute_timer = StepTimer()
    print(
        f"[OpenFHE SS] Computing distances: {actual_n} real candidates, "
        f"batch_size={_BATCH_SIZE}...",
        flush=True,
    )

    py_plain = cc.MakeCKKSPackedPlaintext(py_vals)
    px_plain = cc.MakeCKKSPackedPlaintext(px_vals)

    dy = cc.EvalSub(ct_qy, py_plain)
    dx = cc.EvalSub(ct_qx, px_plain)

    dy2 = cc.EvalMult(dy, dy)
    dx2 = cc.EvalMult(dx, dx)

    dist2_ct = cc.EvalAdd(dy2, dx2)

    # Scale real slots into FHEW range [0, ~0.5]; pad unused slots to 0.9.
    if actual_n < _BATCH_SIZE:
        combined_scale = cc.MakeCKKSPackedPlaintext(
            [_DIST_SCALE] * actual_n + [0.0] * (_BATCH_SIZE - actual_n)
        )
        dist2_scaled = cc.EvalMult(dist2_ct, combined_scale)
        pad_plain = cc.MakeCKKSPackedPlaintext(
            [0.0] * actual_n + [0.9] * (_BATCH_SIZE - actual_n)
        )
        dist2_scaled = cc.EvalAdd(dist2_scaled, pad_plain)
    else:
        scale_plain = cc.MakeCKKSPackedPlaintext([_DIST_SCALE] * _BATCH_SIZE)
        dist2_scaled = cc.EvalMult(dist2_ct, scale_plain)

    compute_ms = compute_timer.elapsed_ms()
    print(f"[OpenFHE SS] Distances computed in {compute_ms:.1f}ms.", flush=True)

    dist_ct_b64 = _serialize_to_b64(dist2_scaled)
    total_ms = total_timer.elapsed_ms()

    return {
        "scheme": "openfhe_ss",
        "dist_ct_b64": dist_ct_b64,
        "candidates": [
            {
                "id": c["id"],
                "name": c["name"],
                "category": c["category"],
                "latitude": c["latitude"],
                "longitude": c["longitude"],
                "lat_m": c["lat_m"],
                "lon_m": c["lon_m"],
            }
            for c in candidates
        ],
        "metrics": {
            "server": {
                "candidate_selection_ms": candidate_ms,
                "computation_ms": compute_ms,
                "total_ms": total_ms,
            },
            "workload": {
                "candidate_count": actual_n,
                "returned_count": 1,
                "k": 1,
                "category": category,
            },
        },
    }
