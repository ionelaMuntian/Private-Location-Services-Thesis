# service_provider_app/app/modules/poi_search/engines/core_concrete.py

import base64
from time import time
from uuid import uuid4

from fastapi import HTTPException

from ....core.concrete_server_runtime import ConcreteServerRuntime
from ....core.metrics import StepTimer
from ..repository import PoiRepository
from ..schemas import (
    ConcreteCandidatesRequest,
    ConcreteEvaluationRequest,
)

repository = PoiRepository()

# Fixed top-2 encrypted sorting circuit.
CONCRETE_CANDIDATE_LIMIT = 2

_CONCRETE_KEY_STORE: dict[str, dict] = {}
CONCRETE_KEY_TTL_SECONDS = 60 * 60

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

    expired_key_ids = [
        key_id
        for key_id, entry in _CONCRETE_KEY_STORE.items()
        if now - float(entry["created_at"]) > CONCRETE_KEY_TTL_SECONDS
    ]

    for key_id in expired_key_ids:
        _CONCRETE_KEY_STORE.pop(key_id, None)


def execute_concrete_upload_keys(evaluation_keys_bytes: bytes) -> dict:
    _cleanup_expired_keys()

    if not evaluation_keys_bytes:
        raise HTTPException(
            status_code=422,
            detail="Concrete evaluation keys are required.",
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


def _resolve_evaluation_keys_bytes(request: ConcreteEvaluationRequest) -> bytes:
    if request.key_id:
        _cleanup_expired_keys()

        entry = _CONCRETE_KEY_STORE.get(request.key_id)
        if entry is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "Concrete key_id was not found or expired. "
                    "Upload the evaluation keys again."
                ),
            )

        return entry["evaluation_keys_bytes"]

    if request.evaluation_keys_b64:
        return base64.b64decode(request.evaluation_keys_b64.encode("utf-8"))

    raise HTTPException(
        status_code=422,
        detail="Concrete evaluation requires either key_id or evaluation_keys_b64.",
    )


def execute_concrete_candidates(request: ConcreteCandidatesRequest) -> dict:
    """
    Returns exactly 2 candidate POIs.

    The Concrete circuit is compiled for fixed top-2 sorting, so the number of
    candidates must match the circuit size.
    """
    total_timer = StepTimer()

    candidate_timer = StepTimer()
    candidates = repository.get_all_by_category(
        category=request.category,
        limit=CONCRETE_CANDIDATE_LIMIT,
    )
    candidate_selection_ms = candidate_timer.elapsed_ms()

    if len(candidates) < 2:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Concrete top-2 sorting requires at least 2 candidates in category "
                f"'{request.category}', but found {len(candidates)}."
            ),
        )

    normalized = [
        {
            "id": item["id"],
            "name": item["name"],
            "category": item["category"],
            "latitude": item["latitude"],
            "longitude": item["longitude"],
            "lat_m": item["lat_m"],
            "lon_m": item["lon_m"],
        }
        for item in candidates[:2]
    ]

    total_ms = total_timer.elapsed_ms()

    return {
        "category": request.category,
        "k": request.k,
        "candidates": normalized,
        "metrics": {
            "server": {
                "candidate_selection_ms": candidate_selection_ms,
                "computation_ms": 0.0,
                "total_ms": total_ms,
            },
            "workload": {
                "candidate_count": len(normalized),
                "returned_count": len(normalized),
                "k": request.k,
                "category": request.category,
            },
        },
    }


def execute_concrete_evaluation(request: ConcreteEvaluationRequest) -> dict:
    """
    Performs server-side encrypted sorting for Concrete.

    The server runs a Concrete circuit that compares the two encrypted distances
    and returns encrypted sorted IDs/distances.

    The client decrypts the already-sorted output. It does not sort.
    """
    total_timer = StepTimer()

    if len(request.items) != 2:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Concrete top-2 sorting requires exactly 2 items, "
                f"but received {len(request.items)}."
            ),
        )

    runtime = _get_runtime()
    evaluation_keys_bytes = _resolve_evaluation_keys_bytes(request)

    evaluation_timer = StepTimer()
    encrypted_sorted_result = runtime.run_sorted_top2_with_key_bytes(
        evaluation_keys_bytes=evaluation_keys_bytes,
        encrypted_user_coords_b64=request.encrypted_user_coords_b64,
        items=request.items,
    )
    evaluation_ms = evaluation_timer.elapsed_ms()
    total_ms = total_timer.elapsed_ms()

    return {
        "scheme": "concrete",
        "encrypted_sorted_result": encrypted_sorted_result,
        "metadata": {
            "requested_k": request.requested_k,
            "candidate_count": len(request.items),
            "top_k_on_server": True,
            "sorting": "encrypted_top2_concrete_circuit",
        },
        "metrics": {
            "server": {
                "evaluation_ms": evaluation_ms,
                "total_ms": total_ms,
            },
            "workload": {
                "candidate_count": len(request.items),
                "returned_count": min(request.requested_k, 2),
                "k": request.requested_k,
                "category": "",
            },
        },
    }