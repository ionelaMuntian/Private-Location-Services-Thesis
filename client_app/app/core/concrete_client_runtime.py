# client_app/app/core/concrete_client_runtime.py

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
        """
        Backward-compatible base64 version.
        The optimized gRPC flow should use serialize_evaluation_keys_bytes().
        """
        self.ensure_keys()
        return _b64encode(self.client.evaluation_keys.serialize())

    def serialize_evaluation_keys_bytes(self) -> bytes:
        """
        Used by streaming gRPC upload.

        This avoids sending Concrete evaluation keys as huge base64 JSON strings.
        """
        self.ensure_keys()
        return self.client.evaluation_keys.serialize()

    def encrypt_user_coords(self, qx: int, qy: int) -> str:
        """
        Encrypts the user's coordinates once.

        Current Concrete circuit signature has 8 inputs:

          qx_rel, qy_rel,
          p1x_rel, p1y_rel, p1_id,
          p2x_rel, p2y_rel, p2_id

        Only qx_rel and qy_rel are encrypted user values.
        The remaining values are clear/public POI inputs, so dummy values are
        passed here only to satisfy client.encrypt().
        """
        self.ensure_keys()

        encrypted_args = self.client.encrypt(
            int(qx),
            int(qy),
            0,
            0,
            1,
            0,
            0,
            2,
        )

        payload = {
            "enc_qx": _b64encode(encrypted_args[0].serialize()),
            "enc_qy": _b64encode(encrypted_args[1].serialize()),
        }

        return _b64encode(json.dumps(payload).encode("utf-8"))

    def decrypt_sorted_top2(self, encrypted_sorted_result: dict) -> list[dict]:
        """
        Decrypts the already-sorted encrypted result returned by the server.

        The client does NOT sort here. The ordering was produced by the Concrete
        circuit on the service-provider side.

        Expected input:
          {
            "first_id": "...",
            "first_dist2": "...",
            "second_id": "...",
            "second_dist2": "..."
          }
        """
        self.ensure_keys()

        first_id_value = fhe.Value.deserialize(
            _b64decode(encrypted_sorted_result["first_id"])
        )
        first_dist2_value = fhe.Value.deserialize(
            _b64decode(encrypted_sorted_result["first_dist2"])
        )
        second_id_value = fhe.Value.deserialize(
            _b64decode(encrypted_sorted_result["second_id"])
        )
        second_dist2_value = fhe.Value.deserialize(
            _b64decode(encrypted_sorted_result["second_dist2"])
        )

        first_id = int(self.client.decrypt(first_id_value))
        first_dist2 = int(self.client.decrypt(first_dist2_value))
        second_id = int(self.client.decrypt(second_id_value))
        second_dist2 = int(self.client.decrypt(second_dist2_value))

        return [
            {
                "id": first_id,
                "dist2": first_dist2,
            },
            {
                "id": second_id,
                "dist2": second_dist2,
            },
        ]