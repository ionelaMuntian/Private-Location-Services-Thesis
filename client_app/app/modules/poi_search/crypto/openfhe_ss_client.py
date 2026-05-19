import math

from .base import ClientCryptoAdapter
from ....core.openfhe_ss_runtime_instance import get_openfhe_ss_runtime


class OpenFHESSClientAdapter(ClientCryptoAdapter):
    """
    Client adapter for CKKS + FHEW scheme-switching nearest-POI search.

    Uses a single fixed-N runtime (N_SS=128) for all categories.  The server
    pads smaller categories to 128 slots with large dummy distances; the client
    restricts the winner search to the first len(candidates) real slots.
    """

    def prepare_query(self, latitude: float, longitude: float, k: int) -> dict:
        rt = get_openfhe_ss_runtime()

        return {
            "plaintext_query": None,
            "encrypted_query": {
                "payload": None,
                "metadata": {
                    "crypto_context_b64": rt.serialize_crypto_context(),
                    "public_key_b64": rt.serialize_public_key(),
                    "eval_mult_keys_b64": rt.serialize_eval_mult_keys(),
                    "encrypted_qy": rt.encrypt_broadcast(float(latitude)),
                    "encrypted_qx": rt.encrypt_broadcast(float(longitude)),
                    "n_candidates": rt.n,
                    "query_encoding": "openfhe_ckks_broadcast_lat_m_lon_m",
                    "distance_metric": "squared_euclidean_meters",
                    "top_k_on_server": True,
                    "requested_k": k,
                },
            },
            "local_state": {
                "latitude_m": latitude,
                "longitude_m": longitude,
                "requested_k": k,
            },
        }

    def parse_response(self, response_data: dict, local_state: dict | None = None) -> list[dict]:
        if local_state is None:
            raise ValueError("OpenFHE SS: missing local_state.")

        rt = get_openfhe_ss_runtime()
        dist2_ct_b64: str = response_data["dist2_ct_b64"]
        candidates: list[dict] = response_data["candidates"]
        actual_n = len(candidates)

        winner_idx = rt.decrypt_argmin_via_ss(dist2_ct_b64, actual_n)

        if winner_idx >= actual_n:
            raise ValueError(
                f"OpenFHE SS: winner index {winner_idx} out of range ({actual_n} candidates)."
            )

        winner = candidates[winner_idx]

        user_lat_m = local_state["latitude_m"]
        user_lon_m = local_state["longitude_m"]
        dy = float(winner.get("lat_m", 0.0)) - user_lat_m
        dx = float(winner.get("lon_m", 0.0)) - user_lon_m
        dist_km = round(math.sqrt(dy * dy + dx * dx) / 1000.0, 4)

        return [
            {
                "id": winner["id"],
                "name": winner["name"],
                "category": winner["category"],
                "latitude": winner["latitude"],
                "longitude": winner["longitude"],
                "distance_km": dist_km,
            }
        ]
