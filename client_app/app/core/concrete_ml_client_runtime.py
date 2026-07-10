import base64
from pathlib import Path

import numpy as np
from concrete.ml.deployment import FHEModelClient

CLIENT_APP_DIR = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = CLIENT_APP_DIR / ".artifacts" / "anomaly_detection"
KEYS_DIR = ARTIFACTS_DIR / "keys"


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def _b64decode(data: str) -> bytes:
    return base64.b64decode(data.encode("utf-8"))


class ConcreteMLClientRuntime:
    def __init__(self) -> None:
        client_zip = ARTIFACTS_DIR / "client.zip"
        if not client_zip.exists():
            raise FileNotFoundError(
                f"Concrete-ML client spec not found at {client_zip}"
                "Rerun the training notebook and rebuild client_app"
            )

        KEYS_DIR.mkdir(parents=True, exist_ok=True)
        self.client = FHEModelClient(path_dir=str(ARTIFACTS_DIR), key_dir=str(KEYS_DIR))
        self._keys_generated = False

    def ensure_keys(self) -> None:
        if not self._keys_generated:
            self.client.generate_private_and_evaluation_keys()
            self._keys_generated = True

    def encrypt_sample(self, features: list[float]) -> tuple[str, str]:
        self.ensure_keys()

        x = np.array([features], dtype=np.float64)
        encrypted_query = self.client.quantize_encrypt_serialize(x)
        evaluation_keys = self.client.get_serialized_evaluation_keys()

        return _b64encode(encrypted_query), _b64encode(evaluation_keys)

    def decrypt_result(self, encrypted_result_b64: str) -> float:
        encrypted_result = _b64decode(encrypted_result_b64)
        result = self.client.deserialize_decrypt_dequantize(encrypted_result)
        return float(np.array(result).reshape(-1)[-1])
