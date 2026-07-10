import base64
import time
from pathlib import Path

from concrete.ml.deployment import FHEModelServer

MODELS_DIR = Path("/models")
FHE_MODEL_DIR = MODELS_DIR / "fhe_model"


def _b64decode(data: str) -> bytes:
    return base64.b64decode(data.encode("utf-8"))


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


class ConcreteMLServerRuntime:
    def __init__(self) -> None:
        self.server: FHEModelServer | None = None

        if (FHE_MODEL_DIR / "server.zip").exists():
            self.server = FHEModelServer(path_dir=str(FHE_MODEL_DIR))
            self.server.load()

    def run(self, encrypted_query_b64: str, evaluation_keys_b64: str) -> dict:
        if self.server is None:
            raise FileNotFoundError(
                f"FHE anomaly-detection server model not found at {FHE_MODEL_DIR}"
                "Rerun the training notebook to produce it"
            )

        encrypted_query = _b64decode(encrypted_query_b64)
        evaluation_keys = _b64decode(evaluation_keys_b64)

        t0 = time.time()
        encrypted_result = self.server.run(encrypted_query, evaluation_keys)
        latency_ms = (time.time() - t0) * 1000

        return {
            "encrypted_result_b64": _b64encode(encrypted_result),
            "latency_ms": latency_ms,
        }
