# client_app/app/modules/poi_search/routes.py
from fastapi import APIRouter, Depends, Query

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


@router.post("/nearest-k", response_model=NearestKResponseType)
async def nearest_k_by_category(
    request: NearestKClientRequest,
    current_user: dict = Depends(get_current_user),
):
    return await service.nearest_k_by_category(request)


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