from .base import ClientCryptoAdapter
from ....core.openfhe_runtime_instance import openfhe_runtime


class OpenFHEClientAdapter(ClientCryptoAdapter):
    def prepare_query(self, latitude: float, longitude: float, k: int) -> dict:
        encrypted_qy = openfhe_runtime.encrypt_scalar(float(latitude))
        encrypted_qx = openfhe_runtime.encrypt_scalar(float(longitude))

        return {
            "plaintext_query": None,
            "encrypted_query": {
                "payload": None,
                "metadata": {
                    "crypto_context": openfhe_runtime.serialize_crypto_context(),
                    "eval_mult_keys": openfhe_runtime.serialize_eval_mult_keys(),
                    "encrypted_qy": encrypted_qy,
                    "encrypted_qx": encrypted_qx,
                    "query_encoding": "openfhe_ckks_scalar_lat_m_lon_m",
                    "distance_metric": "squared_euclidean_meters",
                    "top_k_on_client": True,
                    "requested_k": k,
                },
            },
            "local_state": {
                "requested_k": k,
            },
        }

    def parse_response(self, response_data: dict, local_state: dict | None = None) -> list[dict]:
        if local_state is None:
            raise ValueError("Missing local_state for OpenFHE response parsing.")

        requested_k = int(local_state["requested_k"])

        scored_items = []

        for item in response_data["encrypted_results"]:
            score = openfhe_runtime.decrypt_scalar(item["encrypted_distance"])

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