# service_provider_app/app/modules/poi_search/engines/bfv_engine.py
from .base import ServiceProviderEngine
from ....core.he_engine import (
    dump_bfv_vector,
    load_bfv_vector,
    load_public_context,
)


def encode_bfv_coordinate(value: float, scale: int) -> int:
    return int(round(value * scale))


class BFVEngine(ServiceProviderEngine):
    def compute_nearest_k(self, category: str, k: int, query: dict, candidates: list[dict]) -> dict:
        metadata = query["metadata"]
        public_context = load_public_context(metadata["public_context"])
        encrypted_query = load_bfv_vector(public_context, query["payload"])
        scale = int(metadata["bfv_scale"])

        encrypted_results = []

        for item in candidates:
            py = encode_bfv_coordinate(float(item["lat_m"]), scale)
            px = encode_bfv_coordinate(float(item["lon_m"]), scale)

            diff = encrypted_query - [py, px]
            dist2 = diff.dot(diff)

            encrypted_results.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "category": item["category"],
                    "latitude": item["latitude"],
                    "longitude": item["longitude"],
                    "encrypted_distance": dump_bfv_vector(dist2),
                }
            )

        return {
            "scheme": "bfv",
            "encrypted_results": encrypted_results,
            "metadata": {
                "requested_k": metadata["requested_k"],
                "bfv_scale": scale,
                "distance_metric": "scaled_squared_euclidean_meters",
                "top_k_on_client": True,
            },
        }