from .base import ServiceProviderEngine
from ....core.he_engine import (
    dump_ckks_vector,
    load_ckks_vector,
    load_public_context,
)

class CKKSEngine(ServiceProviderEngine):
    def compute_nearest_k(self, category: str, k: int, query: dict, candidates: list[dict]) -> dict:
        metadata = query["metadata"]
        public_context = load_public_context(metadata["public_context"])
        encrypted_query = load_ckks_vector(public_context, query["payload"])

        encrypted_results = []

        for item in candidates:
            p = [float(item["lat_m"]), float(item["lon_m"])]
            diff = encrypted_query - p
            dist2 = diff.dot(diff)

            encrypted_results.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "category": item["category"],
                    "latitude": item["latitude"],
                    "longitude": item["longitude"],
                    "encrypted_distance": dump_ckks_vector(dist2),
                }
            )

        return {
            "scheme": "ckks",
            "encrypted_results": encrypted_results,
            "metadata": {
                "requested_k": metadata["requested_k"],
                "distance_metric": "squared_euclidean_meters",
                "top_k_on_client": True,
            },
        }