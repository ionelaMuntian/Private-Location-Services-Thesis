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
        Optimized batch evaluation.
          - Deserializes evaluation_keys ONCE
          - Deserializes encrypted (qx, qy) ONCE
          - For each item, runs the FHE distance circuit using the SAME
            encrypted user coordinates and the item's clear (px, py)

        Returns a list of {item fields..., encrypted_distance: <b64>}.
        """
        # Load shared state ONCE
        evaluation_keys = fhe.EvaluationKeys.deserialize(
            _b64decode(evaluation_keys_b64)
        )

        user_payload = json.loads(_b64decode(encrypted_user_coords_b64).decode("utf-8"))
        encrypted_qx = fhe.Value.deserialize(_b64decode(user_payload["enc_qx"]))
        encrypted_qy = fhe.Value.deserialize(_b64decode(user_payload["enc_qy"]))

        results = []
        for item in items:
            px = int(item.px)
            py = int(item.py)

            # In Concrete 2.x, server.run accepts a mix of encrypted Value
            # objects and plain integers (for the 'clear' positions).
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