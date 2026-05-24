# client_app/app/modules/poi_search/service.py
from .scenarios.benchmark import execute_benchmark, get_benchmark_history as _get_benchmark_history
from .scenarios.performance_simulation import (
    execute_performance_simulation as _execute_simulation,
    get_simulation_history as _get_simulation_history,
)
from .scenarios.categories import execute_list_categories
from .scenarios.nearest_k import execute_nearest_k
from .schemas import NearestKClientRequest


class PoiSearchClientService:
    async def nearest_k_by_category(self, request: NearestKClientRequest) -> dict:
        return await execute_nearest_k(request)

    async def list_categories(self) -> dict:
        return await execute_list_categories()

    async def run_benchmark(
        self,
        category: str,
        latitude: float,
        longitude: float,
        k: int,
        schemes: list[str],
        concrete_n_values: list[int],
        openfhe_n_values: list[int] | None = None,
    ) -> dict:
        return await execute_benchmark(
            category=category,
            latitude=latitude,
            longitude=longitude,
            k=k,
            schemes=schemes,
            concrete_n_values=concrete_n_values,
            openfhe_n_values=openfhe_n_values,
        )

    async def get_benchmark_history(self) -> dict:
        return await _get_benchmark_history()

    async def run_performance_simulation(self) -> dict:
        return await _execute_simulation()

    async def get_simulation_history(self) -> dict:
        return await _get_simulation_history()