
# client_app/app/modules/poi_search/crypto/concrete_client.py

from fastapi import HTTPException

from .base import ClientCryptoAdapter
from ....core.concrete_client_runtime import ConcreteClientRuntime
from .quantization import (
    QuantizationConfig,
    dequantize_squared_distance_to_km,
    quantize_metric_coordinate,
)

# For Concrete server-side encrypted sorting, the numeric range must be small.
# Therefore, we use coarser quantization than the old distance-only circuit.
quant_config = QuantizationConfig(scale_divisor=1000)

# Local origin after quantization for the Cluj-Napoca dataset.
# Actual data ranges (÷1000):
#   lon_m_q: 2619..2626  →  relative X: 0..7
#   lat_m_q: 5899..5904  →  relative Y: 0..5
#
# Both ranges fit within [0, 15], the range the Concrete circuit was compiled for.
ORIGIN_X_Q = 2619
ORIGIN_Y_Q = 5899


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
        """
        Prepares the Concrete query for server-side encrypted top-2 sorting.

        The client encrypts only the user coordinates.
        Candidate POI coordinates are public and are sent later as clear inputs.

        Current limitation:
          - The Concrete circuit is compiled for fixed top-2 sorting.
          - Therefore, k can only be 1 or 2.
        """
        if k > 2:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Concrete server-side encrypted sorting currently supports "
                    "only k=1 or k=2 because the circuit is compiled for top-2."
                ),
            )

        runtime = self._create_runtime()

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
                    "requested_k": k,
                    "top_k_on_server": True,
                    "sorting": "encrypted_top2_concrete_circuit",
                    "quantization_scale_divisor": quant_config.scale_divisor,
                    "origin_x_q": ORIGIN_X_Q,
                    "origin_y_q": ORIGIN_Y_Q,
                },
            },
            "local_state": {
                "runtime": runtime,
                "requested_k": k,
                "evaluation_keys_bytes": evaluation_keys_bytes,

                # Maps the small internal IDs used inside the Concrete circuit
                # back to the real database POI records.
                #
                # The circuit should use internal IDs 1 and 2, not real DB IDs,
                # because real DB IDs may be outside the compiled numeric range.
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
        """
        Builds the clear/public POI inputs for the Concrete top-2 circuit.

        Important:
          - User coordinates are NOT included here.
          - POI coordinates are clear because they come from the service provider DB.
          - The circuit uses internal IDs 1 and 2 instead of real database IDs.
        """
        if len(candidates) < 2:
            raise ValueError("Concrete top-2 circuit requires at least 2 candidates.")

        items = []

        for index, candidate in enumerate(candidates[:2], start=1):
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
                    # Internal ID used by the Concrete circuit.
                    # Must stay within the compiled range: 1 or 2.
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
        """
        Parses the Concrete response.

        The server has already performed the encrypted sorting inside the Concrete
        circuit. The client only decrypts the already-sorted IDs/distances and
        maps internal IDs 1/2 back to real POI records.

        No sorting is performed here.
        """
        if local_state is None or "runtime" not in local_state:
            raise ValueError("Missing Concrete runtime in local_state.")

        runtime = local_state["runtime"]
        requested_k = int(local_state["requested_k"])
        candidate_by_internal_id = local_state.get("candidate_by_internal_id", {})

        encrypted_sorted_result = response_data.get("encrypted_sorted_result")
        if encrypted_sorted_result is None:
            raise ValueError("Missing encrypted_sorted_result in Concrete response.")

        # Already sorted by the server-side encrypted Concrete circuit.
        sorted_items = runtime.decrypt_sorted_top2(encrypted_sorted_result)

        results = []

        for sorted_item in sorted_items[:requested_k]:
            internal_id = int(sorted_item["id"])
            dist2_quantized = int(sorted_item["dist2"])

            candidate = candidate_by_internal_id.get(internal_id)
            if candidate is None:
                raise ValueError(
                    f"Decrypted internal POI id {internal_id} was not found "
                    "in candidate_by_internal_id."
                )

            distance_km = dequantize_squared_distance_to_km(
                dist2_quantized,
                quant_config,
            )

            results.append(
                {
                    "id": candidate["id"],
                    "name": candidate["name"],
                    "category": candidate["category"],
                    "latitude": candidate["latitude"],
                    "longitude": candidate["longitude"],
                    "distance_km": distance_km,
                }
            )

        return results