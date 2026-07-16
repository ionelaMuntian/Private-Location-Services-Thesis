import base64
import json
from pathlib import Path

from concrete import fhe

SUPPORTED_N = [1, 5, 12, 13, 14, 15]

def _b64decode(data: str) -> bytes:
    return base64.b64decode(data.encode("utf-8"))


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def _find_server_path(n: int) -> Path:
    current_file = Path(__file__).resolve()
    filename = f"server_n{n}.zip"

    candidates = [
        Path(f"/app/client_app/.artifacts/concrete/{filename}"),
        current_file.parents[3] / "client_app" / ".artifacts" / "concrete" / filename,
        current_file.parents[2] / "client_app" / ".artifacts" / "concrete" / filename,
    ]

    for path in candidates:
        if path.exists():
            return path

    raise FileNotFoundError(
        f"Concrete server artifact for N={n} not found. Checked:\n"
        + "\n".join(str(p) for p in candidates)
        + "\nRun client_app/tools/compile_distance_circuit.py first."
    )


class ConcreteServerRuntime:
    def __init__(self) -> None:
        self._servers: dict[int, fhe.Server] = {}

        for n in SUPPORTED_N:
            try:
                path = _find_server_path(n)
                self._servers[n] = fhe.Server.load(path)
            except FileNotFoundError:
                pass

    def run_find_minimum(self, n: int, evaluation_keys_bytes: bytes, encrypted_user_coords_b64: str, items: list,) -> dict:
        if n not in self._servers:
            raise ValueError(
                f"The concrete server circuit for N={n} is not loaded"
            )

        if len(items) != n:
            raise ValueError(
                f"Concrete circuit for N={n} expects exactly {n} items, "
            )

        server = self._servers[n]
        evaluation_keys = fhe.EvaluationKeys.deserialize(evaluation_keys_bytes)

        user_payload = json.loads( _b64decode(encrypted_user_coords_b64).decode("utf-8") )
        encrypted_qx = fhe.Value.deserialize(_b64decode(user_payload["enc_qx"]))
        encrypted_qy = fhe.Value.deserialize(_b64decode(user_payload["enc_qy"]))

        args: list = [encrypted_qx, encrypted_qy]
        for item in items:
            args += [int(item["px"]), int(item["py"]), int(item["id"])]

        result = server.run(*args, evaluation_keys=evaluation_keys)

        if not isinstance(result, tuple):
            result = (result,)

        if len(result) != 2:
            raise RuntimeError(
                f"Expected 2 encrypted outputs from Concrete N={n} circuit, "
                f"got {len(result)}."
            )

        best_id, best_dist2 = result

        return {
            "best_id": _b64encode(best_id.serialize()),
            "best_dist2": _b64encode(best_dist2.serialize()),
        }
