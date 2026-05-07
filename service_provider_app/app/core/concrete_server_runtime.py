# service_provider_app/app/core/concrete_server_runtime.py

import base64
import json
from pathlib import Path

from concrete import fhe


def _b64decode(data: str) -> bytes:
    return base64.b64decode(data.encode("utf-8"))


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def _find_server_path() -> Path:
    current_file = Path(__file__).resolve()

    candidates = [
        Path("/app/client_app/.artifacts/concrete/server.zip"),
        current_file.parents[3] / "client_app" / ".artifacts" / "concrete" / "server.zip",
        current_file.parents[2] / "client_app" / ".artifacts" / "concrete" / "server.zip",
    ]

    for path in candidates:
        if path.exists():
            return path

    raise FileNotFoundError(
        "Concrete server artifact not found. Checked:\n"
        + "\n".join(str(path) for path in candidates)
        + "\nRun client_app/tools/compile_distance_circuit.py first."
    )


SERVER_PATH = _find_server_path()


class ConcreteServerRuntime:
    def __init__(self) -> None:
        self.server = fhe.Server.load(SERVER_PATH)

    def run_distance_batch(
        self,
        evaluation_keys_b64: str,
        encrypted_user_coords_b64: str,
        items: list,
    ) -> list:
        """
        Backward-compatible version.

        This method receives the Concrete evaluation keys as base64 inside the
        request body. It still works, but it is not recommended because the
        evaluation keys are extremely large and can create huge JSON/gRPC payloads.

        Prefer run_distance_batch_with_key_bytes(), where the keys are uploaded
        separately through streaming gRPC.
        """
        evaluation_keys_bytes = _b64decode(evaluation_keys_b64)

        return self.run_distance_batch_with_key_bytes(
            evaluation_keys_bytes=evaluation_keys_bytes,
            encrypted_user_coords_b64=encrypted_user_coords_b64,
            items=items,
        )

    def run_distance_batch_with_key_bytes(
        self,
        evaluation_keys_bytes: bytes,
        encrypted_user_coords_b64: str,
        items: list,
    ) -> list:
        """
        Optimized Concrete batch evaluation.

        The evaluation keys are received as raw bytes, usually loaded from the
        service-provider key store after they were uploaded once using streaming
        gRPC.

        The server:
          - deserializes evaluation keys once
          - deserializes encrypted user coordinates once
          - evaluates the Concrete distance circuit for each candidate POI
          - returns encrypted distances

        The service provider never sees the plaintext user coordinates.
        """
        evaluation_keys = fhe.EvaluationKeys.deserialize(evaluation_keys_bytes)

        user_payload = json.loads(
            _b64decode(encrypted_user_coords_b64).decode("utf-8")
        )

        encrypted_qx = fhe.Value.deserialize(_b64decode(user_payload["enc_qx"]))
        encrypted_qy = fhe.Value.deserialize(_b64decode(user_payload["enc_qy"]))

        results = []

        for item in items:
            px = int(item.px)
            py = int(item.py)

            result = self.server.run(
                encrypted_qx,
                encrypted_qy,
                px,
                py,
                evaluation_keys=evaluation_keys,
            )

            if isinstance(result, tuple):
                result = result[0]

            results.append(
                {
                    "id": item.id,
                    "name": item.name,
                    "category": item.category,
                    "latitude": item.latitude,
                    "longitude": item.longitude,
                    "encrypted_distance": _b64encode(result.serialize()),
                }
            )

        return results