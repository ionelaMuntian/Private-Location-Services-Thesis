# client_app/app/modules/poi_search/crypto/bfv_client.py
import tenseal as ts

from .base import ClientCryptoAdapter
from ....core.config import settings
from ....core.encryption import (
    BFVContextManager,
    deserialize_bfv_vector,
    serialize_bfv_vector,
)


def encode_bfv_coordinate(value: float, scale: int) -> int:
    return int(round(value * scale))


class BFVClientAdapter(ClientCryptoAdapter):
    def prepare_query(self, latitude: float, longitude: float, k: int) -> dict:
        full_context = BFVContextManager.create_full_context()

        scale = settings.bfv_scale
        qy = encode_bfv_coordinate(float(latitude), scale)
        qx = encode_bfv_coordinate(float(longitude), scale)

        encrypted_query = serialize_bfv_vector(ts.bfv_vector(full_context, [qy, qx]))
        secret_context = BFVContextManager.serialize_secret_context(full_context)

        return {
            "plaintext_query": None,
            "encrypted_query": {
                "payload": encrypted_query,
                "metadata": {
                    # Only send what the server strictly needs to evaluate the HE circuit.
                    # Plaintext coordinates are NEVER included — the server must not learn
                    # the user's location.
                    "public_context": BFVContextManager.serialize_public_context(full_context),
                    "query_encoding": "scaled_lat_m_lon_m_vector",
                    "distance_metric": "scaled_squared_euclidean_meters",
                    "top_k_on_client": True,
                    "requested_k": k,
                    "bfv_scale": scale,
                },
            },
            "local_state": {
                "secret_context": secret_context,
                "requested_k": k,
                "bfv_scale": scale,
            },
        }

    def parse_response(self, response_data: dict, local_state: dict | None = None) -> list[dict]:
        if local_state is None or "secret_context" not in local_state:
            raise ValueError("Missing local_state.secret_context for BFV response parsing.")

        secret_context = BFVContextManager.load_secret_context(local_state["secret_context"])
        requested_k = int(local_state["requested_k"])
        scale = int(local_state["bfv_scale"])

        scored_items = []
        for item in response_data["encrypted_results"]:
            encrypted_score = deserialize_bfv_vector(secret_context, item["encrypted_distance"])
            decrypted = encrypted_score.decrypt()

            dist2_scaled = int(decrypted[0]) if isinstance(decrypted, list) else int(decrypted)
            distance_km = (((max(dist2_scaled, 0)) ** 0.5) / scale) / 1000.0

            scored_items.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "category": item["category"],
                    "latitude": item["latitude"],
                    "longitude": item["longitude"],
                    "distance_km": round(distance_km, 4),
                }
            )

        # Sorting happens on the client after decryption — the server never sees distances.
        scored_items.sort(key=lambda x: x["distance_km"])
        return scored_items[:requested_k]