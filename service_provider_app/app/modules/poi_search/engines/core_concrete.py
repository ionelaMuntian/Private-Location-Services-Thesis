import gc
from time import time
from uuid import uuid4

from fastapi import HTTPException

from ....core.concrete_server_runtime import ConcreteServerRuntime, SUPPORTED_N
from ....core.metrics import StepTimer
from ..repository import PoiRepository
from ..schemas import ConcreteEvaluationRequest

repository = PoiRepository()

_CONCRETE_KEY_STORE: dict[str, dict] = {}

# how long the uploaded Concrete evaluation keys remain stored on the service provider
CONCRETE_KEY_TTL_SECONDS = 60 * 60
_SCALE_DIVISOR = 2200

_runtime: ConcreteServerRuntime | None = None

def _get_runtime() -> ConcreteServerRuntime:
    global _runtime
    if _runtime is None:
        try:
            _runtime = ConcreteServerRuntime()
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Concrete server runtime unavailable: {exc}",
            ) from exc
    return _runtime


def _cleanup_expired_keys() -> None:
    now = time()
    expired = [
        key_id
        for key_id, entry in _CONCRETE_KEY_STORE.items()
        if now - float(entry["created_at"]) > CONCRETE_KEY_TTL_SECONDS
    ]
    for key_id in expired:
        _CONCRETE_KEY_STORE.pop(key_id, None)

def execute_concrete_upload_keys(evaluation_keys_bytes: bytes) -> dict:
    _cleanup_expired_keys()

    if not evaluation_keys_bytes:
        raise HTTPException(
            status_code=422,
            detail="Concrete evaluation keys are required",
        )

    key_id = str(uuid4())
    _CONCRETE_KEY_STORE[key_id] = {
        "evaluation_keys_bytes": evaluation_keys_bytes,
        "created_at": time(),
    }

    return {
        "key_id": key_id,
        "expires_in_seconds": CONCRETE_KEY_TTL_SECONDS,
    }

# returns the eval keys as bytes. It needs either the id or the b64 bytes from the request
def _resolve_evaluation_keys_bytes(request: ConcreteEvaluationRequest) -> bytes:
    if request.key_id:
        _cleanup_expired_keys()
        entry = _CONCRETE_KEY_STORE.get(request.key_id)
        if entry is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Concrete key_id was not found or expired"
                    "Upload the evaluation keys again"
                ),
            )
        return entry["evaluation_keys_bytes"]

    if request.evaluation_keys_b64:
        import base64
        return base64.b64decode(request.evaluation_keys_b64.encode("utf-8"))

    raise HTTPException(
        status_code=422,
        detail="Concrete evaluation requires either key_id or evaluation_keys_b64",
    )

def _quantize(value_m: float) -> int:
    return int(round(value_m / _SCALE_DIVISOR))

def execute_concrete_evaluation(request: ConcreteEvaluationRequest) -> dict:
    n = request.n_candidates

    if n not in SUPPORTED_N:
        raise HTTPException(
            status_code=422,
            detail=(
                f"n_candidates={n} but Concrete circuits are only compiled for "
                f"N ∈ {SUPPORTED_N}"
            ),
        )

    total_timer = StepTimer()
    runtime = _get_runtime()
    evaluation_keys_bytes = _resolve_evaluation_keys_bytes(request)

    candidate_timer = StepTimer()
    rows = repository.get_all_by_category(category=request.category, limit=n)
    actual_n = len(rows)

    if actual_n == 0:
        raise HTTPException(
            status_code=422,
            detail=f"No POIs found for category '{request.category}'",
        )

    candidates = [
        {
            "id": r["id"],
            "name": r["name"],
            "category": r["category"],
            "latitude": r["latitude"],
            "longitude": r["longitude"],
            "lat_m": r["lat_m"],
            "lon_m": r["lon_m"],
        }
        for r in rows
    ]

    # the circuit is compiled for exactly n slots; pad by cycling through the real candidates so every slot maps to a genuine POI
    padded = list(candidates)
    for i in range(n - actual_n):
        padded.append(candidates[i % actual_n])

    items = [
        {
            "px": _quantize(c["lon_m"]),
            "py": _quantize(c["lat_m"]),
            "id": internal_id,
        }
        for internal_id, c in enumerate(padded, start=1)
    ]
    candidate_selection_ms = candidate_timer.elapsed_ms()

    evaluation_timer = StepTimer()
    encrypted_best = runtime.run_find_minimum(
        n=n,
        evaluation_keys_bytes=evaluation_keys_bytes,
        encrypted_user_coords_b64=request.encrypted_user_coords_b64,
        items=items,
    )
    evaluation_ms = evaluation_timer.elapsed_ms()
    total_ms = total_timer.elapsed_ms()

    if request.key_id:
        _CONCRETE_KEY_STORE.pop(request.key_id, None)
    evaluation_keys_bytes = None
    gc.collect()

    return {
        "scheme": "concrete",
        "encrypted_best_result": encrypted_best,
        "candidates": [
            {
                "id": c["id"],
                "name": c["name"],
                "category": c["category"],
                "latitude": c["latitude"],
                "longitude": c["longitude"],
            }
            for c in padded
        ],
        "metadata": {
            "n_candidates": n,
            "top_k_on_server": True,
            "circuit": f"find_minimum_n{n}",
        },
        "metrics": {
            "server": {
                "candidate_selection_ms": candidate_selection_ms,
                "evaluation_ms": evaluation_ms,
                "total_ms": total_ms,
            },
            "workload": {
                "candidate_count": actual_n,
                "returned_count": 1,
                "k": request.requested_k,
                "category": request.category,
            },
        },
    }
