from .base import ServiceProviderEngine


class PlaintextEngine(ServiceProviderEngine):
    def compute_nearest_k(self, category: str, k: int, query: dict, candidates: list[dict]) -> dict:
        latitude = query["latitude"]
        longitude = query["longitude"]

        sorted_candidates = sorted(
            candidates,
            key=lambda item: item["distance_m"] ** 2
        )

        results = []
        for item in sorted_candidates[:k]:
            results.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "category": item["category"],
                    "latitude": item["latitude"],
                    "longitude": item["longitude"],
                    "distance_km": round(item["distance_m"] / 1000.0, 4),
                }
            )

        return {
            "scheme": "plaintext",
            "results": results,
        }