from fastapi import HTTPException

from .base import ClientCryptoAdapter
from ....core.concrete_client_runtime import ConcreteClientRuntime, SUPPORTED_N
from .quantization import (
    QuantizationConfig,
    dequantize_squared_distance_to_km,
    quantize_metric_coordinate,
)

quant_config = QuantizationConfig(scale_divisor=2200)

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
                detail=(
                    f"Concrete circuit is compiled for N ∈ {SUPPORTED_N}"
                    f"Requested N={n} is not supported"
                ),
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
                "candidate_by_internal_id": {},
                "quantization_scale_divisor": quant_config.scale_divisor,
                "origin_x_q": ORIGIN_X_Q,
                "origin_y_q": ORIGIN_Y_Q,
            },
        }

    def build_public_args_for_candidates(
        self,
        metadata: dict,
        candidates: list[dict],
        local_state: dict,
    ) -> list[dict]:
        n = int(local_state["n_candidates"])
        actual_n = len(candidates)

        if actual_n == 0:
            raise ValueError("Concrete: no candidates returned for the category")

        padded = list(candidates)
        for i in range(n - actual_n):
            padded.append(candidates[i % actual_n])

        items = []

        for index, candidate in enumerate(padded, start=1):
            px = (
                quantize_metric_coordinate(float(candidate["lon_m"]), quant_config)
                - ORIGIN_X_Q
            )
            py = (
                quantize_metric_coordinate(float(candidate["lat_m"]), quant_config)
                - ORIGIN_Y_Q
            )

            internal_id = int(index)
            real_id = int(candidate["id"])

            local_state["candidate_by_internal_id"][internal_id] = {
                "id": real_id,
                "name": candidate["name"],
                "category": candidate["category"],
                "latitude": candidate["latitude"],
                "longitude": candidate["longitude"],
            }

            items.append(
                {
                    "id": internal_id,
                    "name": candidate["name"],
                    "category": candidate["category"],
                    "latitude": candidate["latitude"],
                    "longitude": candidate["longitude"],
                    "px": int(px),
                    "py": int(py),
                }
            )

        return items

    def parse_response(
        self,
        response_data: dict,
        local_state: dict | None = None,
    ) -> list[dict]:
        if local_state is None or "runtime" not in local_state:
            raise ValueError("Missing Concrete runtime in local_state")

        runtime: ConcreteClientRuntime = local_state["runtime"]
        candidate_by_internal_id = local_state.get("candidate_by_internal_id", {})

        encrypted_best = response_data.get("encrypted_best_result")
        if encrypted_best is None:
            raise ValueError("Missing encrypted_best_result in Concrete response")

        best = runtime.decrypt_top1(encrypted_best)

        internal_id = int(best["id"])
        dist2_quantized = int(best["dist2"])

        n = local_state.get("n_candidates", "?")
        candidate = candidate_by_internal_id.get(internal_id)
        if candidate is None:
            raise ValueError(
                f"Concrete PBS noise error: decrypted id={internal_id} is outside"
                f"valid range [1..{n}]. Recompile with a lower p_error"
            )

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
