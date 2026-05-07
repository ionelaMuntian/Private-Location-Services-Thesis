# service_provider_app/app/modules/poi_search/engines/core_concrete.py
from fastapi import HTTPException

from ....core.concrete_server_runtime import ConcreteServerRuntime
from ....core.metrics import StepTimer
from ..repository import PoiRepository
from ..schemas import (
    ConcreteCandidatesRequest,
    ConcreteEvaluationRequest,
)

repository = PoiRepository()


def execute_concrete_candidates(request: ConcreteCandidatesRequest) -> dict:
    """
    Round 1 of the Concrete protocol.

    Returns ALL POIs in the requested category — no user location is used.
    """
    total_timer = StepTimer()

    candidate_timer = StepTimer()
    candidates = repository.get_all_by_category(
        category=request.category,
        limit=1000,
    )
    candidate_selection_ms = candidate_timer.elapsed_ms()

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
        for item in candidates
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
    Round 2 of the Concrete protocol — optimized batch version.

    The server receives:
      - evaluation_keys_b64: FHE evaluation keys (loaded ONCE)
      - encrypted_user_coords_b64: encrypted (qx, qy) (loaded ONCE)
      - items: list of POI candidates with CLEAR (px, py) integers

    The server evaluates the FHE distance circuit for each POI and returns
    the encrypted results. It never sees plaintext user coordinates.
    """
    total_timer = StepTimer()

    try:
        runtime = ConcreteServerRuntime()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Concrete server runtime unavailable: {exc}",
        ) from exc

    evaluation_timer = StepTimer()
    encrypted_results = runtime.run_distance_batch(
        evaluation_keys_b64=request.evaluation_keys_b64,
        encrypted_user_coords_b64=request.encrypted_user_coords_b64,
        items=request.items,
    )
    evaluation_ms = evaluation_timer.elapsed_ms()
    total_ms = total_timer.elapsed_ms()

    return {
        "scheme": "concrete",
        "encrypted_results": encrypted_results,
        "metadata": {
            "requested_k": request.requested_k,
            "candidate_count": len(request.items),
            "top_k_on_client": True,
        },
        "metrics": {
            "server": {
                "evaluation_ms": evaluation_ms,
                "total_ms": total_ms,
            },
            "workload": {
                "candidate_count": len(request.items),
                "returned_count": len(encrypted_results),
                "k": request.requested_k,
                "category": "",
            },
        },
    }