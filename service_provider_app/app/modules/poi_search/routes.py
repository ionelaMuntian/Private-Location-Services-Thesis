# service_provider_app/app/modules/poi_search/routes.py
from fastapi import APIRouter, Query

from .schemas import (
    CategoryListResponse,
    ConcreteCandidatesRequest,
    ConcreteCandidatesResponse,
    ConcreteEvaluationRequest,
    ConcreteEvaluationResponse,
    PoiNameSearchResponse,
    ServiceProviderNearestKRequest,
    ServiceProviderNearestKResponse,
)
from .service import PoiSearchServiceProviderService

router = APIRouter()
service = PoiSearchServiceProviderService()


@router.post("/nearest-k", response_model=ServiceProviderNearestKResponse)
def nearest_k_by_category(request: ServiceProviderNearestKRequest):
    return service.nearest_k_by_category(request)


@router.get("/categories", response_model=CategoryListResponse)
def list_categories():
    return service.list_categories()


@router.post("/concrete/candidates", response_model=ConcreteCandidatesResponse)
def concrete_candidates(request: ConcreteCandidatesRequest):
    return service.concrete_candidates(request)


@router.post("/concrete/evaluate", response_model=ConcreteEvaluationResponse)
def concrete_evaluate(request: ConcreteEvaluationRequest):
    return service.concrete_evaluate(request)


@router.get("/search-by-name", response_model=PoiNameSearchResponse)
def search_by_name(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
):
    return service.search_by_name(query=q, limit=limit)