import math

from .base import ClientCryptoAdapter
from ....core.openfhe_ss_runtime_instance import get_openfhe_ss_runtime

def _epsg3857_to_wgs84(lat_m: float, lon_m: float) -> tuple[float, float]:
    lon_deg = lon_m / 20037508.342789244 * 180.0
    lat_rad = 2.0 * math.atan(math.exp(lat_m / 6378137.0)) - math.pi / 2.0
    return math.degrees(lat_rad), lon_deg

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return round(R * 2.0 * math.asin(math.sqrt(a)), 4)

class OpenFHESSClientAdapter(ClientCryptoAdapter):
    def prepare_query(self, latitude: float, longitude: float, k: int, n: int) -> dict:
        rt = get_openfhe_ss_runtime(n)

        return {
            "plaintext_query": None,
            "encrypted_query": {
                "payload": None,
                "metadata": {
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
                "n_candidates": n,
            },
        }

    def parse_response(self, response_data: dict, local_state: dict | None = None) -> list[dict]:
        if local_state is None:
            raise ValueError("OpenFHE SS: missing local_state.")

        rt = get_openfhe_ss_runtime(local_state["n_candidates"])
        dist_ct_b64: str = response_data["dist_ct_b64"]
        candidates: list[dict] = response_data["candidates"]
        actual_n = len(candidates)

        winner_idx = rt.eval_min_scheme_switching(dist_ct_b64, actual_n)

        if winner_idx >= actual_n:
            raise ValueError(
                f"OpenFHE SS: winner index {winner_idx} out of range ({actual_n} candidates)."
            )

        winner = candidates[winner_idx]

        _LAT_REF_M = 5_891_000.0
        _LON_REF_M = 2_617_000.0
        user_lat_deg, user_lon_deg = _epsg3857_to_wgs84(
            local_state["latitude_m"] + _LAT_REF_M,
            local_state["longitude_m"] + _LON_REF_M,
        )
        dist_km = _haversine_km(
            user_lat_deg, user_lon_deg,
            float(winner["latitude"]), float(winner["longitude"]),
        )

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
