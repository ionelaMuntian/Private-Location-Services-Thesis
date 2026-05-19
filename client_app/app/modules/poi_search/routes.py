# client_app/app/modules/poi_search/routes.py
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from ..auth.dependencies import get_current_user
from .schemas import (
    CategoryListResponse,
    NearestKClientRequest,
    NearestKResponseType,
    PoiNameSearchResponse,
)
from .service import PoiSearchClientService

router = APIRouter()
service = PoiSearchClientService()


class BenchmarkRequest(BaseModel):
    category: str
    latitude_m: float
    longitude_m: float
    k: int = Field(1, ge=1, le=50)
    schemes: list[str] = ["plaintext", "ckks", "bfv", "openfhe"]
    concrete_n_values: list[int] = [1, 2, 5, 10]


@router.post("/nearest-k", response_model=NearestKResponseType)
async def nearest_k_by_category(
    request: NearestKClientRequest,
    current_user: dict = Depends(get_current_user),
):
    return await service.nearest_k_by_category(request)


@router.post("/benchmark")
async def run_benchmark(
    request: BenchmarkRequest,
    current_user: dict = Depends(get_current_user),
):
    return await service.run_benchmark(
        category=request.category,
        latitude_m=request.latitude_m,
        longitude_m=request.longitude_m,
        k=request.k,
        schemes=request.schemes,
        concrete_n_values=request.concrete_n_values,
    )


@router.get("/categories", response_model=CategoryListResponse)
async def list_categories(
    current_user: dict = Depends(get_current_user),
):
    return await service.list_categories()


@router.get("/search-by-name", response_model=PoiNameSearchResponse)
async def search_by_name(
    q: str = Query(..., min_length=1),
    limit: int = Query(10, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
    return await service.search_by_name(query=q, limit=limit)