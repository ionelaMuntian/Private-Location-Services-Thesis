import base64
import tempfile
from pathlib import Path
from typing import Any

from openfhe import *


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def _b64decode(data: str) -> bytes:
    return base64.b64decode(data.encode("utf-8"))


def _serialize_to_b64(obj: Any) -> str:
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        path = tmp.name

    try:
        if not SerializeToFile(path, obj, BINARY):
            raise RuntimeError(f"OpenFHE failed to serialize object to {path}")
        data = Path(path).read_bytes()
        return _b64encode(data)
    finally:
        Path(path).unlink(missing_ok=True)


def _write_b64_to_temp_file(payload_b64: str) -> str:
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(_b64decode(payload_b64))
        return tmp.name


class OpenFHEClientRuntime:
    def __init__(self) -> None:
        self.cc = self._create_context()
        self.keys = self.cc.KeyGen()
        self.cc.EvalMultKeyGen(self.keys.secretKey)

    def _create_context(self):
        parameters = CCParamsCKKSRNS()
        parameters.SetMultiplicativeDepth(2)
        parameters.SetScalingModSize(50)
        parameters.SetBatchSize(1)

        cc = GenCryptoContext(parameters)
        cc.Enable(PKESchemeFeature.PKE)
        cc.Enable(PKESchemeFeature.KEYSWITCH)
        cc.Enable(PKESchemeFeature.LEVELEDSHE)

        return cc

    def serialize_crypto_context(self) -> str:
        return _serialize_to_b64(self.cc)

    def serialize_eval_mult_keys(self) -> str:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            path = tmp.name

        try:
            if not self.cc.SerializeEvalMultKey(path, BINARY):
                raise RuntimeError("OpenFHE failed to serialize EvalMult keys.")
            data = Path(path).read_bytes()
            return _b64encode(data)
        finally:
            Path(path).unlink(missing_ok=True)

    def encrypt_scalar(self, value: float) -> str:
        plaintext = self.cc.MakeCKKSPackedPlaintext([float(value)])
        ciphertext = self.cc.Encrypt(self.keys.publicKey, plaintext)
        return _serialize_to_b64(ciphertext)

    def decrypt_scalar(self, ciphertext_b64: str) -> float:
        path = _write_b64_to_temp_file(ciphertext_b64)

        try:
            ciphertext, ok = DeserializeCiphertext(path, BINARY)
            if not ok:
                raise RuntimeError("OpenFHE failed to deserialize ciphertext.")

            plaintext = self.cc.Decrypt(ciphertext, self.keys.secretKey)
            plaintext.SetLength(1)

            values = plaintext.GetRealPackedValue()
            return float(values[0])
        finally:
            Path(path).unlink(missing_ok=True)