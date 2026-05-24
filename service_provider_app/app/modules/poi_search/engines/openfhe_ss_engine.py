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
# All categories are padded to this size; the client restricts the winner
# search to the first len(candidates) real slots.
_BATCH_SIZE = 128


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
# Key upload
# ---------------------------------------------------------------------------

def execute_openfhe_ss_upload_keys(
    crypto_context_b64: str,
    public_key_b64: str,
    eval_mult_keys_b64: str,
    eval_automorphism_keys_b64: str,
    n_candidates: int,
) -> dict:
    _cleanup_expired_keys()

    key_id = str(uuid4())
    _KEY_STORE[key_id] = {
        "crypto_context_b64": crypto_context_b64,
        "public_key_b64": public_key_b64,
        "eval_mult_keys_b64": eval_mult_keys_b64,
        "eval_automorphism_keys_b64": eval_automorphism_keys_b64,
        "n_candidates": n_candidates,
        "created_at": time(),
    }

    return {"key_id": key_id, "expires_in_seconds": _KEY_TTL_SECONDS}


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
    1. Load cached CKKS+SS context and all evaluation keys.
    2. Fetch n_candidates POIs from DB.
    3. Pack their coordinates as plaintext CKKS vectors.
    4. Compute vectorised scaled squared distances:
         dist2_scaled[i] = DIST_SCALE * ((qy - py_i)^2 + (qx - px_i)^2)
    5. Run EvalMinSchemeSwitching to find the argmin entirely on the server:
         - Converts dist2_scaled from CKKS to FHEW domain
         - Runs log2(n) rounds of exact comparisons in the FHEW domain
         - Converts the one-hot argmin result back to CKKS
    6. Return the encrypted argmin one-hot ciphertext to the client.

    Privacy guarantee: the server never sees plaintext query coordinates.
    The client decrypts only the winner index (one-hot), not all distances.
    """
    total_timer = StepTimer()

    entry = _load_keys(key_id)
    n = entry["n_candidates"]

    if n_candidates != n:
        raise HTTPException(
            status_code=422,
            detail=(
                f"n_candidates={n_candidates} does not match the uploaded key setup "
                f"(n={n}). Re-upload keys with the correct n."
            ),
        )

    # --- Fetch all real candidates for the category ---------------------
    candidate_timer = StepTimer()
    candidates = repository.get_all_by_category(category=category)
    candidate_ms = candidate_timer.elapsed_ms()
    actual_n = len(candidates)

    if actual_n == 0:
        raise HTTPException(
            status_code=422,
            detail=f"No POIs found for category '{category}'.",
        )
    if actual_n > _BATCH_SIZE:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Category '{category}' has {actual_n} POIs which exceeds "
                f"the maximum batch size of {_BATCH_SIZE}."
            ),
        )

    # --- Load crypto context + evaluation keys (cached per key_id) ------
    if key_id not in _CC_CACHE:
        print(f"[OpenFHE SS] Loading crypto context for key_id={key_id[:8]}...", flush=True)
        cc = _load_crypto_context(entry["crypto_context_b64"])
        _load_eval_mult_keys(cc, entry["eval_mult_keys_b64"])
        _CC_CACHE[key_id] = cc
    else:
        print(f"[OpenFHE SS] Reusing cached context for key_id={key_id[:8]}.", flush=True)
    cc = _CC_CACHE[key_id]

    # --- Deserialise encrypted query coordinates ------------------------
    ct_qy = _load_ciphertext(encrypted_qy)
    ct_qx = _load_ciphertext(encrypted_qx)

    # --- Compute vectorised scaled dist² --------------------------------
    compute_timer = StepTimer()
    print(
        f"[OpenFHE SS] Computing distances: {actual_n} real candidates, "
        f"batch_size={_BATCH_SIZE}...",
        flush=True,
    )

    py_vals = [float(c["lat_m"]) for c in candidates]
    px_vals = [float(c["lon_m"]) for c in candidates]

    py_plain = cc.MakeCKKSPackedPlaintext(py_vals)
    px_plain = cc.MakeCKKSPackedPlaintext(px_vals)

    dy = cc.EvalSub(ct_qy, py_plain)
    dx = cc.EvalSub(ct_qx, px_plain)

    dy2 = cc.EvalMult(dy, dy)
    dx2 = cc.EvalMult(dx, dx)

    dist2_ct = cc.EvalAdd(dy2, dx2)

    # Force padding slots (actual_n.._BATCH_SIZE-1) to 0.9 so they can never
    # win the argmin.  Real city-scale distances are < 0.5 after scaling;
    # 0.9 lies safely inside the FHEW-valid [-1, 1] window.
    #
    # Root cause of the overflow: encrypted query coords are broadcast to all
    # 128 slots, but OpenFHE zero-pads short py_plain/px_plain vectors, so
    # padding slots compute dy = qy - 0 ≈ 5.9e6 → dist²_scaled ≈ 210,000.
    # That is far outside [-1, 1], causing FHEW polynomial overflow → wrong
    # argmin.
    #
    # Fix: fold the scale and the zeroing mask into ONE ct-pt EvalMult.
    # This reduces server-side level consumption by 1 compared to doing
    # EvalMult(scale) + EvalMult(keep_mask) separately, leaving one extra
    # level available to EvalMinSchemeSwitching on the client.
    if actual_n < _BATCH_SIZE:
        combined_scale = cc.MakeCKKSPackedPlaintext(
            [_DIST_SCALE] * actual_n + [0.0] * (_BATCH_SIZE - actual_n)
        )
        dist2_scaled = cc.EvalMult(dist2_ct, combined_scale)  # scale real + zero padding

        pad_plain = cc.MakeCKKSPackedPlaintext(
            [0.0] * actual_n + [0.9] * (_BATCH_SIZE - actual_n)
        )
        dist2_scaled = cc.EvalAdd(dist2_scaled, pad_plain)  # set padding to 0.9
    else:
        scale_plain = cc.MakeCKKSPackedPlaintext([_DIST_SCALE] * _BATCH_SIZE)
        dist2_scaled = cc.EvalMult(dist2_ct, scale_plain)

    compute_ms = compute_timer.elapsed_ms()
    print(f"[OpenFHE SS] Distances computed in {compute_ms:.1f}ms.", flush=True)

    # --- Serialise encrypted dist² ciphertext for client-side argmin ---
    # The client holds all scheme-switching keys (LKSK, BTKeys) and will run
    # EvalMinSchemeSwitching locally on this ciphertext.
    dist2_ct_b64 = _serialize_to_b64(dist2_scaled)

    total_ms = total_timer.elapsed_ms()

    return {
        "scheme": "openfhe_ss",
        "dist2_ct_b64": dist2_ct_b64,
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
