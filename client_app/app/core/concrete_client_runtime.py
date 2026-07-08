import base64
import json
from pathlib import Path

from concrete import fhe

CLIENT_APP_DIR = Path(__file__).resolve().parents[2]
ARTIFACTS_DIR = CLIENT_APP_DIR / ".artifacts" / "concrete"

SUPPORTED_N = [1, 5, 12, 13, 14, 15]


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def _b64decode(data: str) -> bytes:
    return base64.b64decode(data.encode("utf-8"))


def _specs_path(n: int) -> Path:
    return ARTIFACTS_DIR / f"client_specs_n{n}.bin"


class ConcreteClientRuntime:

    def __init__(self, n: int) -> None:
        if n not in SUPPORTED_N:
            raise ValueError(
                f"Unsupported N={n}. Supported values: {SUPPORTED_N}"
                "Recompile the circuits if you need a different N"
            )

        self.n = n
        path = _specs_path(n)

        if not path.exists():
            raise FileNotFoundError(
                f"Concrete client specs are not found at {path}"
                f"Run client_app/tools/compile_distance_circuit.py first"
            )

        specs_bytes = path.read_bytes()
        self.client_specs = fhe.ClientSpecs.deserialize(specs_bytes)
        self.client = fhe.Client(self.client_specs)
        self._keys_generated = False

    def ensure_keys(self) -> None:
        if not self._keys_generated:
            self.client.keygen()
            self._keys_generated = True

    def serialize_evaluation_keys_bytes(self) -> bytes:
        self.ensure_keys()
        return self.client.evaluation_keys.serialize()

    def encrypt_user_coords(self, qx: int, qy: int) -> str:
        self.ensure_keys()

        args: list = [int(qx), int(qy)]
        for i in range(1, self.n + 1):
            args += [0, 0, i]

        encrypted_args = self.client.encrypt(*args)

        payload = {
            "enc_qx": _b64encode(encrypted_args[0].serialize()),
            "enc_qy": _b64encode(encrypted_args[1].serialize()),
        }
        return _b64encode(json.dumps(payload).encode("utf-8"))

    def decrypt_top1(self, encrypted_result: dict) -> dict:
        self.ensure_keys()

        best_id_value = fhe.Value.deserialize(_b64decode(encrypted_result["best_id"]))
        best_dist2_value = fhe.Value.deserialize(
            _b64decode(encrypted_result["best_dist2"])
        )

        best_id, best_dist2 = self.client.decrypt(best_id_value, best_dist2_value)

        return {
            "id": int(best_id),
            "dist2": int(best_dist2),
        }
