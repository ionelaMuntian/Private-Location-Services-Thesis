# client_app/app/core/openfhe_multiparty_runtime.py
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


def _deserialize_ciphertext(ciphertext_b64: str):
    path = _write_b64_to_temp_file(ciphertext_b64)

    try:
        ciphertext, ok = DeserializeCiphertext(path, BINARY)
        if not ok:
            raise RuntimeError("OpenFHE failed to deserialize ciphertext.")
        return ciphertext
    finally:
        Path(path).unlink(missing_ok=True)


class OpenFHEMultipartyRuntime:
    """
    Demo two-party OpenFHE multiparty runtime.

    Parties:
      - user / employee
      - company

    The service provider receives:
      - crypto context
      - joint public key
      - evaluation multiplication keys

    The service provider never receives:
      - user secret key share
      - company secret key share

    In this thesis demo, both secret shares live inside the trusted client_app
    process. For a production system, the user share and company share should
    live on separate trusted clients/devices.
    """

    def __init__(self) -> None:
        self.cc = self._create_context()

        self.user_keys = self.cc.KeyGen()
        self.company_keys = self.cc.MultipartyKeyGen(self.user_keys.publicKey)

        self.joint_public_key = self.company_keys.publicKey

        self._generate_eval_mult_keys()

    def _create_context(self):
        parameters = CCParamsCKKSRNS()
        parameters.SetMultiplicativeDepth(3)
        parameters.SetScalingModSize(50)
        parameters.SetBatchSize(1)

        cc = GenCryptoContext(parameters)
        cc.Enable(PKESchemeFeature.PKE)
        cc.Enable(PKESchemeFeature.KEYSWITCH)
        cc.Enable(PKESchemeFeature.LEVELEDSHE)
        cc.Enable(PKESchemeFeature.MULTIPARTY)

        return cc

    def _generate_eval_mult_keys(self) -> None:
        """
        Generates multiparty evaluation multiplication keys.

        This follows the standard OpenFHE threshold-FHE pattern.
        Depending on your installed OpenFHE Python version, the exact method names
        may differ slightly. The logic is:
          1. user creates first eval key
          2. company extends it
          3. both eval keys are added
          4. the joined eval key is inserted in the context
        """
        eval_mult_key_user = self.cc.KeySwitchGen(
            self.user_keys.secretKey,
            self.user_keys.secretKey,
        )

        eval_mult_key_company = self.cc.MultiKeySwitchGen(
            self.company_keys.secretKey,
            self.company_keys.secretKey,
            eval_mult_key_user,
        )

        eval_mult_key_joint = self.cc.MultiAddEvalKeys(
            eval_mult_key_user,
            eval_mult_key_company,
            self.company_keys.publicKey.GetKeyTag(),
        )

        self.cc.InsertEvalMultKey([eval_mult_key_joint])

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
        ciphertext = self.cc.Encrypt(self.joint_public_key, plaintext)
        return _serialize_to_b64(ciphertext)

    def user_partial_decrypt_scalar(self, ciphertext_b64: str) -> str:
        ciphertext = _deserialize_ciphertext(ciphertext_b64)

        partials = self.cc.MultipartyDecryptLead(
            [ciphertext],
            self.user_keys.secretKey,
        )

        return _serialize_to_b64(partials[0])

    def company_partial_decrypt_scalar(self, ciphertext_b64: str) -> str:
        ciphertext = _deserialize_ciphertext(ciphertext_b64)

        partials = self.cc.MultipartyDecryptMain(
            [ciphertext],
            self.company_keys.secretKey,
        )

        return _serialize_to_b64(partials[0])

    def company_fuse_scalar(
        self,
        user_partial_b64: str,
        company_partial_b64: str,
    ) -> float:
        user_partial = _deserialize_ciphertext(user_partial_b64)
        company_partial = _deserialize_ciphertext(company_partial_b64)

        plaintext = self.cc.MultipartyDecryptFusion(
            [user_partial, company_partial]
        )

        plaintext.SetLength(1)
        values = plaintext.GetRealPackedValue()

        return float(values[0])