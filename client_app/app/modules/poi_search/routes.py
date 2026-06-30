from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ..auth.dependencies import get_current_user
from .schemas import (
    CategoryListResponse,
    NearestKClientRequest,
    NearestKResponseType,
)
from .service import PoiSearchClientService

router = APIRouter()
service = PoiSearchClientService()


class BenchmarkRequest(BaseModel):
    category: str
    latitude: float
    longitude: float
    k: int = Field(1, ge=1, le=50)
    schemes: list[str] = ["plaintext", "ckks", "concrete", "openfhe_ss"]
    concrete_n_values: list[int] = []
    openfhe_n_values: list[int] = []


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
        latitude=request.latitude,
        longitude=request.longitude,
        k=request.k,
        schemes=request.schemes,
        concrete_n_values=request.concrete_n_values,
        openfhe_n_values=request.openfhe_n_values,
    )


@router.get("/categories", response_model=CategoryListResponse)
async def list_categories(
    current_user: dict = Depends(get_current_user),
):
    return await service.list_categories()


@router.post("/simulate-performance")
async def run_performance_simulation(
    current_user: dict = Depends(get_current_user),
):
    return await service.run_performance_simulation()


@router.get("/simulate-performance/history")
async def get_simulation_history(
    current_user: dict = Depends(get_current_user),
):
    return await service.get_simulation_history()


@router.get("/benchmark/history")
async def get_benchmark_history(
    current_user: dict = Depends(get_current_user),
):
    return await service.get_benchmark_history()


