# client_app/app/modules/poi_search/scenarios/benchmark.py

from ..schemas import NearestKClientRequest
from .nearest_k import execute_nearest_k

SUPPORTED_STANDARD_SCHEMES = ["plaintext", "ckks", "bfv", "openfhe"]
SUPPORTED_CONCRETE_N = [1, 2, 5, 10, 20]


async def execute_benchmark(
    category: str,
    latitude_m: float,
    longitude_m: float,
    k: int,
    schemes: list[str],
    concrete_n_values: list[int],
) -> dict:
    runs = []

    for scheme in schemes:
        if scheme not in SUPPORTED_STANDARD_SCHEMES:
            continue

        request = NearestKClientRequest(
            category=category,
            k=k,
            latitude_m=latitude_m,
            longitude_m=longitude_m,
            scheme=scheme,
        )

        result = await execute_nearest_k(request)

        runs.append(
            {
                "label": scheme,
                "scheme": scheme,
                "n_candidates": result.get("metrics", {}).get("workload", {}).get("candidate_count"),
                "timing": result.get("metrics", {}),
                "sizes": result.get("sizes", {}),
            }
        )

    for n in concrete_n_values:
        if n not in SUPPORTED_CONCRETE_N:
            continue

        request = NearestKClientRequest(
            category=category,
            k=1,
            latitude_m=latitude_m,
            longitude_m=longitude_m,
            scheme="concrete",
            n_candidates=n,
        )

        result = await execute_nearest_k(request)

        runs.append(
            {
                "label": f"concrete (N={n})",
                "scheme": "concrete",
                "n_candidates": n,
                "timing": result.get("metrics", {}),
                "sizes": result.get("sizes", {}),
            }
        )

    return {
        "category": category,
        "latitude_m": latitude_m,
        "longitude_m": longitude_m,
        "runs": runs,
    }
