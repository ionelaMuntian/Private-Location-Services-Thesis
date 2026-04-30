#C:\Users\Mariana Ionela\MATERII\AN 4 - UTCN\LICENTA - PYTHON\client_app\app\core\concrete_client_runtime.py
import base64
from pathlib import Path

from concrete import fhe


CLIENT_APP_DIR = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = CLIENT_APP_DIR / ".artifacts" / "concrete"
CLIENT_SPECS_PATH = ARTIFACTS_DIR / "client_specs.bin"


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def _b64decode(data: str) -> bytes:
    return base64.b64decode(data.encode("utf-8"))


class ConcreteClientRuntime:
    def __init__(self) -> None:
        if not CLIENT_SPECS_PATH.exists():
            raise FileNotFoundError(
                f"Concrete client specs not found at {CLIENT_SPECS_PATH}. "
                "Run client_app/tools/compile_distance_circuit.py first."
            )

        specs_bytes = CLIENT_SPECS_PATH.read_bytes()
        self.client_specs = fhe.ClientSpecs.deserialize(specs_bytes)
        self.client = fhe.Client(self.client_specs)
        self._keys_generated = False

    def ensure_keys(self) -> None:
        if not self._keys_generated:
            self.client.keygen()
            self._keys_generated = True

    def serialize_evaluation_keys(self) -> str:
        self.ensure_keys()
        return _b64encode(self.client.evaluation_keys.serialize())

    def encrypt_distance_call(self, qx: int, qy: int, px: int, py: int) -> str:
        self.ensure_keys()

        encrypted_args, public_args = self.client.encrypt(qx, qy, px, py)

        if encrypted_args is not None:
            raise ValueError(
                "Expected no separate encrypted args for this circuit, but got some."
            )

        return _b64encode(public_args.serialize())

    def decrypt_distance(self, serialized_public_result_b64: str) -> int:
        self.ensure_keys()
        public_result = fhe.PublicResult.deserialize(_b64decode(serialized_public_result_b64))
        result = self.client.decrypt(public_result)
        return int(result)