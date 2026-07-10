import base64
import gc
import tempfile
from pathlib import Path
from time import time
from typing import Any
from uuid import uuid4

from fastapi import HTTPException

import openfhe
from openfhe import (
    BINARY,
    DeserializeCiphertext,
    DeserializeCryptoContext,
    ReleaseAllContexts,
    SerializeToFile,
)

_DeserializePublicKey = getattr(openfhe, "DeserializePublicKey", None)

_FLEXIBLEAUTO = getattr(openfhe, "FLEXIBLEAUTO",
                        getattr(openfhe, "ScalingTechnique", openfhe).FLEXIBLEAUTO)

from ....core.metrics import StepTimer
from ..repository import PoiRepository

_KEY_TTL_SECONDS = 60 * 60
_KEY_STORE: dict[str, dict] = {}

_CC_CACHE: dict[str, Any] = {}

repository = PoiRepository()

_DIST_SCALE = 5e-9
_N_VALUES = 128


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


def execute_openfhe_ss_upload_keys(
    crypto_context_b64: str,
    public_key_b64: str,
    eval_mult_keys_b64: str,
    n_candidates: int,
    eval_automorphism_keys_b64: str = "",
    fhew_context_b64: str = "",
) -> dict:
    _cleanup_expired_keys()

    key_id = str(uuid4())

    ReleaseAllContexts()
    _CC_CACHE.clear()

    cc = _load_crypto_context(crypto_context_b64)
    _load_eval_mult_keys(cc, eval_mult_keys_b64)

    _KEY_STORE[key_id] = {
        "public_key_b64": public_key_b64,
        "n_candidates": n_candidates,
        "created_at": time(),
    }
    _CC_CACHE[key_id] = cc

    return {
        "key_id": key_id,
        "expires_in_seconds": _KEY_TTL_SECONDS,
        "status": "ready",
    }


def _load_keys(key_id: str) -> dict:
    _cleanup_expired_keys()
    entry = _KEY_STORE.get(key_id)
    if entry is None:
        raise HTTPException(
            status_code=404,
            detail="OpenFHE SS key_id not found or expired. Re-upload keys",
        )
    return entry


def _load_crypto_context(context_b64: str):
    path = _write_b64_to_temp(context_b64)
    try:
        cc, ok = DeserializeCryptoContext(path, BINARY)
        if not ok:
            raise RuntimeError("OpenFHE SS: failed to deserialize CryptoContext")
        return cc
    finally:
        Path(path).unlink(missing_ok=True)


def _load_eval_mult_keys(cc, emk_b64: str) -> None:
    path = _write_b64_to_temp(emk_b64)
    try:
        try:
            if not cc.DeserializeEvalMultKey(path, BINARY):
                raise RuntimeError("OpenFHE SS: failed to deserialize EvalMult keys")
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
                raise RuntimeError("OpenFHE SS: failed to deserialize EvalAutomorphism keys")
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
            raise RuntimeError("OpenFHE SS: failed to deserialize ciphertext")
        return ct
    finally:
        Path(path).unlink(missing_ok=True)


def _load_public_key(pk_b64: str):
    if _DeserializePublicKey is None:
        raise RuntimeError("OpenFHE SS: DeserializePublicKey not found in openfhe module")
    path = _write_b64_to_temp(pk_b64)
    try:
        pk, ok = _DeserializePublicKey(path, BINARY)
        if not ok:
            raise RuntimeError("OpenFHE SS: failed to deserialize public key")
        return pk
    finally:
        Path(path).unlink(missing_ok=True)


# Evaluation

def execute_openfhe_ss_evaluate(
    key_id: str,
    encrypted_qy: str,
    encrypted_qx: str,
    category: str,
    n_candidates: int,
) -> dict:
    total_timer = StepTimer()

    entry = _load_keys(key_id)
    n = entry["n_candidates"]

    if n_candidates != n:
        raise HTTPException(
            status_code=422,
            detail=(
                f"n_candidates={n_candidates} does not match the uploaded key setup "
                f"(n={n}). Re-upload keys"
            ),
        )

    candidate_timer = StepTimer()
    rows = repository.get_all_by_category(category=category, limit=n)
    actual_n = len(rows)
    if actual_n == 0:
        raise HTTPException(
            status_code=404,
            detail=f"No POIs found for category '{category}'",
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

    while len(py_vals) < n:
        py_vals.append(0.0)
        px_vals.append(0.0)
    py_vals = py_vals[:n]
    px_vals = px_vals[:n]

    candidate_ms = candidate_timer.elapsed_ms()

    cc = _CC_CACHE.get(key_id)
    if cc is None:
        raise HTTPException(status_code=404, detail="OpenFHE SS: CC not in cache")

    ct_qy = _load_ciphertext(encrypted_qy)
    ct_qx = _load_ciphertext(encrypted_qx)

    compute_timer = StepTimer()

    py_plain = cc.MakeCKKSPackedPlaintext(py_vals)
    px_plain = cc.MakeCKKSPackedPlaintext(px_vals)

    dy = cc.EvalSub(ct_qy, py_plain)
    dx = cc.EvalSub(ct_qx, px_plain)

    dy2 = cc.EvalMult(dy, dy)
    dx2 = cc.EvalMult(dx, dx)

    dist2_ct = cc.EvalAdd(dy2, dx2)

    if actual_n < n:
        combined_scale = cc.MakeCKKSPackedPlaintext(
            [_DIST_SCALE] * actual_n + [0.0] * (n - actual_n)
        )
        dist2_scaled = cc.EvalMult(dist2_ct, combined_scale)
        pad_plain = cc.MakeCKKSPackedPlaintext(
            [0.0] * actual_n + [0.9] * (n - actual_n)
        )
        dist2_scaled = cc.EvalAdd(dist2_scaled, pad_plain)
    else:
        scale_plain = cc.MakeCKKSPackedPlaintext([_DIST_SCALE] * n)
        dist2_scaled = cc.EvalMult(dist2_ct, scale_plain)

    compute_ms = compute_timer.elapsed_ms()

    dist_ct_b64 = _serialize_to_b64(dist2_scaled)
    total_ms = total_timer.elapsed_ms()

    _KEY_STORE.pop(key_id, None)
    _CC_CACHE.pop(key_id, None)
    gc.collect()

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
