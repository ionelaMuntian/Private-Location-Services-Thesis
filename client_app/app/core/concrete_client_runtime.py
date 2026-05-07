#C:\Users\Mariana Ionela\MATERII\AN 4 - UTCN\LICENTA - PYTHON\client_app\app\core\concrete_client_runtime.py
import base64
import json
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

    def encrypt_user_coords(self, qx: int, qy: int) -> str:
        """
        Encrypts the user's (qx, qy) ONCE per query.
        Returns a base64-encoded JSON payload with the two encrypted Value objects.

        Format:
          {
            "enc_qx": "<b64 of Value>",
            "enc_qy": "<b64 of Value>"
          }
        """
        self.ensure_keys()

        # client.encrypt expects same number of args as the circuit signature
        # (4 args). For this call we only care about the first two (encrypted).
        # Pass dummy 0s for the clear positions; we will not transmit them.
        encrypted_args = self.client.encrypt(int(qx), int(qy), 0, 0)

        payload = {
            "enc_qx": _b64encode(encrypted_args[0].serialize()),
            "enc_qy": _b64encode(encrypted_args[1].serialize()),
        }
        return _b64encode(json.dumps(payload).encode("utf-8"))

    def decrypt_distance(self, serialized_public_result_b64: str) -> int:
        self.ensure_keys()
        public_result = fhe.Value.deserialize(
            _b64decode(serialized_public_result_b64)
        )
        result = self.client.decrypt(public_result)
        return int(result)