from .base import ServiceProviderEngine
from ....core.openfhe_engine import (
    dump_ciphertext,
    load_ciphertext,
    load_crypto_context,
    load_eval_mult_keys,
)


class OpenFHEEngine(ServiceProviderEngine):
    def compute_nearest_k(self, category: str, k: int, query: dict, candidates: list[dict]) -> dict:
        metadata = query["metadata"]

        cc = load_crypto_context(metadata["crypto_context"])
        load_eval_mult_keys(cc, metadata["eval_mult_keys"])

        encrypted_qy = load_ciphertext(metadata["encrypted_qy"])
        encrypted_qx = load_ciphertext(metadata["encrypted_qx"])

        encrypted_results = []

        for item in candidates:
            py_plain = cc.MakeCKKSPackedPlaintext([float(item["lat_m"])])
            px_plain = cc.MakeCKKSPackedPlaintext([float(item["lon_m"])])

            dy = cc.EvalSub(encrypted_qy, py_plain)
            dx = cc.EvalSub(encrypted_qx, px_plain)

            dy2 = cc.EvalMult(dy, dy)
            dx2 = cc.EvalMult(dx, dx)

            dist2 = cc.EvalAdd(dy2, dx2)

            encrypted_results.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "category": item["category"],
                    "latitude": item["latitude"],
                    "longitude": item["longitude"],
                    "encrypted_distance": dump_ciphertext(dist2),
                }
            )

        return {
            "scheme": "openfhe",
            "encrypted_results": encrypted_results,
            "metadata": {
                "requested_k": metadata["requested_k"],
                "distance_metric": "squared_euclidean_meters",
                "top_k_on_client": True,
            },
        }