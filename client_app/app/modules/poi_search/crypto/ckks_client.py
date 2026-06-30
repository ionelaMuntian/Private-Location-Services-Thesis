import tenseal as ts

from .base import ClientCryptoAdapter
from ....core.encryption import (
    CKKSContextManager,
    deserialize_ckks_vector,
    serialize_ckks_vector,
)


class CKKSClientAdapter(ClientCryptoAdapter):
    def prepare_query(self, latitude: float, longitude: float, k: int) -> dict:
        full_context = CKKSContextManager.create_full_context()

        query_vector = [float(latitude), float(longitude)]
        encrypted_query = serialize_ckks_vector(ts.ckks_vector(full_context, query_vector))

        secret_context = CKKSContextManager.serialize_secret_context(full_context)

        return {
            "plaintext_query": None,
            "encrypted_query": {
                "payload": encrypted_query,
                "metadata": {
                    "public_context": CKKSContextManager.serialize_public_context(full_context),
                    "query_encoding": "lat_m_lon_m_vector",
                    "distance_metric": "squared_euclidean_meters",
                    "top_k_on_client": True,
                    "requested_k": k,
                },
            },
            "local_state": {
                "secret_context": secret_context,
                "requested_k": k,
            },
        }

    def parse_response(self, response_data: dict, local_state: dict | None = None) -> list[dict]:
        if local_state is None or "secret_context" not in local_state:
            raise ValueError("Missing local_state.secret_context for CKKS response parsing.")

        secret_context = CKKSContextManager.load_secret_context(local_state["secret_context"])
        requested_k = int(local_state["requested_k"])

        scored_items = []
        for item in response_data["encrypted_results"]:
            encrypted_score = deserialize_ckks_vector(secret_context, item["encrypted_distance"])
            decrypted = encrypted_score.decrypt()

            score = float(decrypted[0]) if isinstance(decrypted, list) else float(decrypted)

            scored_items.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "category": item["category"],
                    "latitude": item["latitude"],
                    "longitude": item["longitude"],
                    "distance_km": round((max(score, 0.0) ** 0.5) / 1000.0, 4),
                }
            )

        scored_items.sort(key=lambda x: x["distance_km"])
        return scored_items[:requested_k]