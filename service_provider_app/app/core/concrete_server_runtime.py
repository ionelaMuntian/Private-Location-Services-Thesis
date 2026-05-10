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

    def run_sorted_top2_with_key_bytes(
        self,
        evaluation_keys_bytes: bytes,
        encrypted_user_coords_b64: str,
        items: list,
    ) -> dict:
        """
        Runs the fixed top-2 Concrete sorting circuit.

        The server performs the comparison and ordering inside the FHE circuit.
        It does not learn which POI is closer because the sorted IDs and
        distances are encrypted outputs.
        """
        if len(items) < 2:
            raise ValueError("Concrete server-side sorting requires exactly 2 candidates.")

        item1 = items[0]
        item2 = items[1]

        evaluation_keys = fhe.EvaluationKeys.deserialize(evaluation_keys_bytes)

        user_payload = json.loads(
            _b64decode(encrypted_user_coords_b64).decode("utf-8")
        )

        encrypted_qx = fhe.Value.deserialize(_b64decode(user_payload["enc_qx"]))
        encrypted_qy = fhe.Value.deserialize(_b64decode(user_payload["enc_qy"]))

        result = self.server.run(
            encrypted_qx,
            encrypted_qy,
            int(item1.px),
            int(item1.py),
            int(item1.id),
            int(item2.px),
            int(item2.py),
            int(item2.id),
            evaluation_keys=evaluation_keys,
        )

        if not isinstance(result, tuple):
            result = (result,)

        if len(result) != 4:
            raise RuntimeError(
                f"Expected 4 encrypted outputs from Concrete top-2 circuit, got {len(result)}."
            )

        first_id, first_dist2, second_id, second_dist2 = result

        return {
            "first_id": _b64encode(first_id.serialize()),
            "first_dist2": _b64encode(first_dist2.serialize()),
            "second_id": _b64encode(second_id.serialize()),
            "second_dist2": _b64encode(second_dist2.serialize()),
        }