# service_provider_app/app/modules/poi_search/scenarios/nearest_k.py
from fastapi import HTTPException

from ....core.metrics import StepTimer
from ..engines.bfv_engine import BFVEngine
from ..engines.ckks_engine import CKKSEngine
from ..engines.concrete_engine import ConcreteEngine
from ..engines.plaintext_engine import PlaintextEngine
from ..repository import PoiRepository
from ..schemas import ServiceProviderNearestKRequest

repository = PoiRepository()

def get_engine(scheme: str):
    if scheme == "plaintext":
        return PlaintextEngine()
    if scheme == "ckks":
        return CKKSEngine()
    if scheme == "bfv":
        return BFVEngine()
    if scheme == "concrete":
        return ConcreteEngine()
    raise HTTPException(status_code=400, detail=f"Unsupported scheme: {scheme}")


def execute_nearest_k(request: ServiceProviderNearestKRequest) -> dict:
    total_timer = StepTimer()

    if request.scheme == "plaintext":
        if request.plaintext_query is None:
            raise HTTPException(
                status_code=422,
                detail="plaintext_query is required for plaintext mode.",
            )

        candidate_timer = StepTimer()
        results = repository.get_by_category_nearest_k_plaintext(
            category=request.category,
            k=request.k,
            latitude_m=request.plaintext_query.latitude_m,
            longitude_m=request.plaintext_query.longitude_m,
        )
        candidate_selection_ms = candidate_timer.elapsed_ms()

        total_ms = total_timer.elapsed_ms()

        return {
            "scheme": request.scheme,
            "results": results,
            "metrics": {
                "server": {
                    "candidate_selection_ms": candidate_selection_ms,
                    "computation_ms": 0.0,
                    "total_ms": total_ms,
                },
                "workload": {
                    "candidate_count": len(results),
                    "returned_count": len(results),
                    "k": request.k,
                    "category": request.category,
                },
            },
        }

    if request.scheme in {"ckks", "bfv", "concrete"}:
        if request.encrypted_query is None:
            raise HTTPException(
                status_code=422,
                detail=f"encrypted_query is required for {request.scheme} mode.",
            )

        candidate_timer = StepTimer()
        candidates = repository.get_candidates_by_category(
            category=request.category,
            latitude_m=request.encrypted_query.metadata["query_latitude_m"],
            longitude_m=request.encrypted_query.metadata["query_longitude_m"],
            limit=max(request.k * 20, 200),
        )
        candidate_selection_ms = candidate_timer.elapsed_ms()

        compute_timer = StepTimer()
        engine = get_engine(request.scheme)
        engine_result = engine.compute_nearest_k(
            category=request.category,
            k=request.k,
            query={
                "payload": request.encrypted_query.payload,
                "metadata": request.encrypted_query.metadata,
            },
            candidates=candidates,
        )
        computation_ms = compute_timer.elapsed_ms()

        total_ms = total_timer.elapsed_ms()

        engine_result["metrics"] = {
            "server": {
                "candidate_selection_ms": candidate_selection_ms,
                "computation_ms": computation_ms,
                "total_ms": total_ms,
            },
            "workload": {
                "candidate_count": len(candidates),
                "returned_count": len(engine_result.get("results", []) or engine_result.get("encrypted_results", [])),
                "k": request.k,
                "category": request.category,
            },
        }
        return engine_result

    raise HTTPException(
        status_code=501,
        detail=f"Scheme {request.scheme} is not enabled.",
    )