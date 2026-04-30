# service_provider_app/app/core/concrete_server_runtime.py
import base64
from pathlib import Path

from concrete import fhe


def _b64decode(data: str) -> bytes:
    return base64.b64decode(data.encode("utf-8"))


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def _find_server_path() -> Path:
    current_file = Path(__file__).resolve()

    candidates = [
        # Docker path
        Path("/app/client_app/.artifacts/concrete/server.zip"),

        # Local project root path
        current_file.parents[3] / "client_app" / ".artifacts" / "concrete" / "server.zip",

        # Fallback if running directly from service_provider_app
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

    def run_distance(
        self,
        serialized_evaluation_keys_b64: str,
        serialized_public_args_b64: str,
    ) -> str:
        evaluation_keys = fhe.EvaluationKeys.deserialize(
            _b64decode(serialized_evaluation_keys_b64)
        )
        public_args = fhe.PublicArguments.deserialize(
            _b64decode(serialized_public_args_b64)
        )

        public_result = self.server.run(public_args, evaluation_keys)
        return _b64encode(public_result.serialize())