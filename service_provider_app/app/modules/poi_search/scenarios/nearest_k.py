from fastapi import HTTPException
from ....core.metrics import StepTimer
from ..engines.concrete_engine import ConcreteEngine
from ..engines.plaintext_engine import PlaintextEngine
from ..repository import PoiRepository
from ..schemas import ServiceProviderNearestKRequest

repository = PoiRepository()

def get_engine(scheme: str):
    if scheme == "plaintext":
        return PlaintextEngine()
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
        candidate_count = repository.count_by_category(request.category)
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
                    "candidate_count": candidate_count,
                    "returned_count": len(results),
                    "k": request.k,
                    "category": request.category,
                },
            },
        }

    if request.scheme == "concrete":
        raise HTTPException(
            status_code=400,
            detail=(
                "Concrete uses a dedicated two-round protocol"
                "Use POST /concrete/candidates then POST /concrete/evaluate"
            ),
        )

    raise HTTPException(
        status_code=501,
        detail=f"Scheme {request.scheme} is not enabled",
    )