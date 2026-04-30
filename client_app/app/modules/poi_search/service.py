# client_app/app/modules/poi_search/service.py
from .scenarios.categories import execute_list_categories
from .scenarios.nearest_k import execute_nearest_k
from .scenarios.search_by_name import execute_search_by_name
from .schemas import NearestKClientRequest


class PoiSearchClientService:
    async def nearest_k_by_category(self, request: NearestKClientRequest) -> dict:
        return await execute_nearest_k(request)

    async def list_categories(self) -> dict:
        return await execute_list_categories()

    async def search_by_name(self, query: str, limit: int = 10) -> dict:
        return await execute_search_by_name(query=query, limit=limit)