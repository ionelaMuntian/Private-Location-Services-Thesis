import math

from .base import ClientCryptoAdapter
from ....core.openfhe_ss_runtime_instance import get_openfhe_ss_runtime


class OpenFHESSClientAdapter(ClientCryptoAdapter):
    """
    Client adapter for CKKS + FHEW scheme-switching nearest-POI search.

    prepare_query() uploads:
      - CKKS crypto context (includes BinFHE context + BTKeys)
      - public key
      - eval-mult keys
      - encrypted query coordinates (broadcast ciphertexts)

    parse_response() expects:
      - dist2_ct_b64: str    — encrypted squared-distance ciphertext from server
      - candidates: list[dict] — POI metadata with lat_m/lon_m for distance computation

    The client runs EvalMinSchemeSwitching locally on the received dist² ciphertext
    to find the argmin without decrypting all distances.
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
                    "eval_automorphism_keys_b64": rt.serialize_eval_automorphism_keys(),
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
                "n_candidates": rt.n,
            },
        }

    def parse_response(self, response_data: dict, local_state: dict | None = None) -> list[dict]:
        if local_state is None:
            raise ValueError("OpenFHE SS: missing local_state.")

        rt = get_openfhe_ss_runtime()
        dist2_ct_b64: str = response_data["dist2_ct_b64"]
        candidates: list[dict] = response_data["candidates"]

        winner_idx = rt.decrypt_argmin_via_ss(dist2_ct_b64)

        if winner_idx >= len(candidates):
            raise ValueError(
                f"OpenFHE SS: winner index {winner_idx} out of range "
                f"({len(candidates)} candidates)."
            )

        winner = candidates[winner_idx]

        # Compute distance from user coordinates to winner (metric projection)
        user_lat_m = local_state["latitude_m"]
        user_lon_m = local_state["longitude_m"]

        # Candidates include lat_m/lon_m (projected metres) for distance computation
        winner_lat_m = float(winner.get("lat_m", 0.0))
        winner_lon_m = float(winner.get("lon_m", 0.0))

        dy = winner_lat_m - user_lat_m
        dx = winner_lon_m - user_lon_m
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
