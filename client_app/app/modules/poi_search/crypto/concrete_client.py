# client_app/app/modules/poi_search/crypto/concrete_client.py
from fastapi import HTTPException

from .base import ClientCryptoAdapter
from ....core.concrete_client_runtime import ConcreteClientRuntime
from .quantization import (
    QuantizationConfig,
    dequantize_squared_distance_to_km,
    quantize_metric_coordinate,
)

quant_config = QuantizationConfig(scale_divisor=100)

# Local origin after quantization.
# Dataset area:
# lon_m ≈ 2362254 -> 23622 after /100
# lat_m ≈ 5741384 -> 57414 after /100
ORIGIN_X_Q = 23600
ORIGIN_Y_Q = 57400


class ConcreteClientAdapter(ClientCryptoAdapter):
    def _create_runtime(self) -> ConcreteClientRuntime:
        try:
            return ConcreteClientRuntime()
        except Exception as exc:
            raise HTTPException(
                status_code=503,
                detail=f"Concrete client runtime unavailable: {exc}",
            ) from exc

    def prepare_query(self, latitude: float, longitude: float, k: int) -> dict:
        runtime = self._create_runtime()

        qx = quantize_metric_coordinate(float(longitude), quant_config) - ORIGIN_X_Q
        qy = quantize_metric_coordinate(float(latitude), quant_config) - ORIGIN_Y_Q

        return {
            "plaintext_query": None,
            "encrypted_query": {
                "payload": None,
                "metadata": {
                    "evaluation_keys": runtime.serialize_evaluation_keys(),
                    "requested_k": k,
                    "top_k_on_client": True,
                },
            },
            "local_state": {
                "runtime": runtime,
                "requested_k": k,
                "qx": qx,
                "qy": qy,
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
        runtime = local_state["runtime"]

        qx = int(local_state["qx"])
        qy = int(local_state["qy"])

        items = []
        for candidate in candidates:
            px = (
                quantize_metric_coordinate(float(candidate["lon_m"]), quant_config)
                - ORIGIN_X_Q
            )
            py = (
                quantize_metric_coordinate(float(candidate["lat_m"]), quant_config)
                - ORIGIN_Y_Q
            )

            public_args_b64 = runtime.encrypt_distance_call(qx, qy, px, py)

            items.append(
                {
                    "id": candidate["id"],
                    "name": candidate["name"],
                    "category": candidate["category"],
                    "latitude": candidate["latitude"],
                    "longitude": candidate["longitude"],
                    "public_args_b64": public_args_b64,
                }
            )

        return items

    def parse_response(self, response_data: dict, local_state: dict | None = None) -> list[dict]:
        if local_state is None or "runtime" not in local_state:
            raise ValueError("Missing Concrete runtime in local_state.")

        runtime = local_state["runtime"]
        requested_k = int(local_state["requested_k"])

        scored_items = []
        for item in response_data["encrypted_results"]:
            dist2_quantized = runtime.decrypt_distance(item["encrypted_distance"])
            distance_km = dequantize_squared_distance_to_km(
                dist2_quantized,
                quant_config,
            )

            scored_items.append(
                {
                    "id": item["id"],
                    "name": item["name"],
                    "category": item["category"],
                    "latitude": item["latitude"],
                    "longitude": item["longitude"],
                    "distance_km": distance_km,
                }
            )

        scored_items.sort(key=lambda x: x["distance_km"])
        return scored_items[:requested_k]