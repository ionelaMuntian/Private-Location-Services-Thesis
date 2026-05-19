# client_app/app/modules/poi_search/service.py
from .scenarios.benchmark import execute_benchmark
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

    async def run_benchmark(
        self,
        category: str,
        latitude_m: float,
        longitude_m: float,
        k: int,
        schemes: list[str],
        concrete_n_values: list[int],
    ) -> dict:
        return await execute_benchmark(
            category=category,
            latitude_m=latitude_m,
            longitude_m=longitude_m,
            k=k,
            schemes=schemes,
            concrete_n_values=concrete_n_values,
        )