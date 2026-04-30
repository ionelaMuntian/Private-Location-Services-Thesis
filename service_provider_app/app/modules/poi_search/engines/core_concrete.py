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
    total_timer = StepTimer()

    candidate_timer = StepTimer()
    candidates = repository.get_candidates_by_category(
        category=request.category,
        latitude_m=request.latitude_m,
        longitude_m=request.longitude_m,
        limit=max(request.k * 20, 200),
    )
    candidate_selection_ms = candidate_timer.elapsed_ms()

    normalized = []
    for item in candidates:
        normalized.append(
            {
                "id": item["id"],
                "name": item["name"],
                "category": item["category"],
                "latitude": item["latitude"],
                "longitude": item["longitude"],
                "lat_m": item["lat_m"],
                "lon_m": item["lon_m"],
            }
        )

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
    total_timer = StepTimer()

    try:
        runtime = ConcreteServerRuntime()
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Concrete server runtime unavailable: {exc}",
        ) from exc

    evaluation_timer = StepTimer()
    encrypted_results = []

    for item in request.items:
        encrypted_distance = runtime.run_distance(
            serialized_evaluation_keys_b64=request.evaluation_keys_b64,
            serialized_public_args_b64=item.public_args_b64,
        )

        encrypted_results.append(
            {
                "id": item.id,
                "name": item.name,
                "category": item.category,
                "latitude": item.latitude,
                "longitude": item.longitude,
                "encrypted_distance": encrypted_distance,
            }
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