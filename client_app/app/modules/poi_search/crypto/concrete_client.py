from fastapi import HTTPException

from .base import ClientCryptoAdapter
from ....core.concrete_client_runtime import ConcreteClientRuntime, SUPPORTED_N
from .quantization import (
    QuantizationConfig,
    dequantize_squared_distance_to_km,
    quantize_metric_coordinate,
)

quant_config = QuantizationConfig(scale_divisor=2200)

# values for stripping the prefix of the coordinates
_LAT_REF_M = 5_891_000.0
_LON_REF_M = 2_617_000.0

ORIGIN_X_Q = 0
ORIGIN_Y_Q = 0

class ConcreteClientAdapter(ClientCryptoAdapter):
    def _create_runtime(self, n: int) -> ConcreteClientRuntime:
        try:
            return ConcreteClientRuntime(n)
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Concrete client runtime unavailable for N={n}: {exc}",
            ) from exc

    def prepare_query(self, latitude: float, longitude: float, k: int, n: int = 2) -> dict:
        if n not in SUPPORTED_N:
            raise HTTPException(
                status_code=422,
                detail=( f"Concrete circuit is compiled for N = {SUPPORTED_N} " ),
            )

        runtime = self._create_runtime(n)

        qx = quantize_metric_coordinate(float(longitude), quant_config) - ORIGIN_X_Q
        qy = quantize_metric_coordinate(float(latitude), quant_config) - ORIGIN_Y_Q

        encrypted_user_coords_b64 = runtime.encrypt_user_coords(qx, qy)
        evaluation_keys_bytes = runtime.serialize_evaluation_keys_bytes()

        return {
            "plaintext_query": None,
            "encrypted_query": {
                "payload": None,
                "metadata": {
                    "encrypted_user_coords": encrypted_user_coords_b64,
                    "n_candidates": n,
                    "top_k_on_server": True,
                    "sorting": f"encrypted_min_concrete_n{n}",
                    "quantization_scale_divisor": quant_config.scale_divisor,
                    "origin_x_q": ORIGIN_X_Q,
                    "origin_y_q": ORIGIN_Y_Q,
                },
            },
            "local_state": {
                "runtime": runtime,
                "n_candidates": n,
                "evaluation_keys_bytes": evaluation_keys_bytes,
                "quantization_scale_divisor": quant_config.scale_divisor,
                "origin_x_q": ORIGIN_X_Q,
                "origin_y_q": ORIGIN_Y_Q,
            },
        }

    def parse_response(
        self,
        response_data: dict,
        local_state: dict | None = None,
    ) -> list[dict]:
        if local_state is None or "runtime" not in local_state:
            raise ValueError("Missing Concrete runtime in local_state")

        runtime: ConcreteClientRuntime = local_state["runtime"]

        encrypted_best = response_data.get("encrypted_best_result")
        if encrypted_best is None:
            raise ValueError("Missing encrypted_best_result in Concrete response")

        candidates = response_data.get("candidates") or []

        best = runtime.decrypt_top1(encrypted_best)

        internal_id = int(best["id"])
        dist2_quantized = int(best["dist2"])

        if not (1 <= internal_id <= len(candidates)):
            raise ValueError(
                f"Concrete PBS noise error: decrypted id={internal_id} is outside "
                f"valid range [1..{len(candidates)}]. Recompile with a lower p_error"
            )

        candidate = candidates[internal_id - 1]

        distance_km = dequantize_squared_distance_to_km(dist2_quantized, quant_config)

        return [
            {
                "id": candidate["id"],
                "name": candidate["name"],
                "category": candidate["category"],
                "latitude": candidate["latitude"],
                "longitude": candidate["longitude"],
                "distance_km": distance_km,
            }
        ]
