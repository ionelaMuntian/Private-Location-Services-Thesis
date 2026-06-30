import base64
import tempfile
from pathlib import Path
from typing import Any

from openfhe import *

KEYS_DIR = Path("/app/keys")

_CC_FILE  = KEYS_DIR / "crypto_context.bin"
_USER_PK_FILE = KEYS_DIR / "user_public_key.bin"
_USER_SK_FILE  = KEYS_DIR / "user_secret_key.bin"
_COMPANY_PK_FILE = KEYS_DIR / "company_public_key.bin"
_COMPANY_SK_FILE = KEYS_DIR / "company_secret_key.bin"
_EVAL_MULT_FILE  = KEYS_DIR / "eval_mult_keys.bin"

_ALL_KEY_FILES = [
    _CC_FILE,
    _USER_PK_FILE,
    _USER_SK_FILE,
    _COMPANY_PK_FILE,
    _COMPANY_SK_FILE,
    _EVAL_MULT_FILE,
]

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


def _try_set_multiparty_noise_mode(parameters) -> None:
    pass


class OpenFHEMultipartyRuntime:

    def __init__(self) -> None:
        KEYS_DIR.mkdir(parents=True, exist_ok=True)

        if all(f.exists() for f in _ALL_KEY_FILES):
            print("[OpenFHE] Loading persisted keys from disk", flush=True)
            self._load_from_disk()
        else:
            print("[OpenFHE] No persisted keys found, generating new key pair", flush=True)
            self._generate_and_save()

    # Key generation + persistence
    def _create_context(self):
        parameters = CCParamsCKKSRNS()
        parameters.SetMultiplicativeDepth(5)
        parameters.SetScalingModSize(50)
        parameters.SetBatchSize(1)

        _try_set_multiparty_noise_mode(parameters)

        cc = GenCryptoContext(parameters)
        cc.Enable(PKESchemeFeature.PKE)
        cc.Enable(PKESchemeFeature.KEYSWITCH)
        cc.Enable(PKESchemeFeature.LEVELEDSHE)
        cc.Enable(PKESchemeFeature.MULTIPARTY)

        return cc

    def _generate_eval_mult_keys(self) -> None:
        eval_mult_key_user = self.cc.KeySwitchGen(
            self._user_sk,
            self._user_sk,
        )

        eval_mult_key_company = self.cc.MultiKeySwitchGen(
            self._company_sk,
            self._company_sk,
            eval_mult_key_user,
        )

        eval_mult_key_joint = self.cc.MultiAddEvalMultKeys(
            eval_mult_key_user,
            eval_mult_key_company,
            self.joint_public_key.GetKeyTag(),
        )

        self.cc.InsertEvalMultKey([eval_mult_key_joint])

    def _generate_and_save(self) -> None:
        self.cc = self._create_context()

        user_keys    = self.cc.KeyGen()
        company_keys = self.cc.MultipartyKeyGen(user_keys.publicKey)

        self._user_sk         = user_keys.secretKey
        self._company_sk      = company_keys.secretKey
        self.joint_public_key = company_keys.publicKey

        self._generate_eval_mult_keys()
        self._save_to_disk()

    def _save_to_disk(self) -> None:
        SerializeToFile(str(_CC_FILE),         self.cc,                  BINARY)
        SerializeToFile(str(_USER_SK_FILE),    self._user_sk,            BINARY)
        SerializeToFile(str(_COMPANY_SK_FILE), self._company_sk,         BINARY)
        SerializeToFile(str(_COMPANY_PK_FILE), self.joint_public_key,    BINARY)
        SerializeToFile(str(_USER_PK_FILE),    self.joint_public_key,    BINARY)
        self.cc.SerializeEvalMultKey(str(_EVAL_MULT_FILE), BINARY)
        print("[OpenFHE] Keys saved to disk", flush=True)

    def _load_from_disk(self) -> None:
        cc, ok = DeserializeCryptoContext(str(_CC_FILE), BINARY)
        if not ok:
            raise RuntimeError("Failed to load OpenFHE crypto context from disk")
        self.cc = cc

        if not self.cc.DeserializeEvalMultKey(str(_EVAL_MULT_FILE), BINARY):
            raise RuntimeError("Failed to load OpenFHE eval mult keys from disk")

        joint_pk, ok = DeserializePublicKey(str(_COMPANY_PK_FILE), BINARY)
        if not ok:
            raise RuntimeError("Failed to load joint public key from disk")
        self.joint_public_key = joint_pk

        user_sk, ok = DeserializePrivateKey(str(_USER_SK_FILE), BINARY)
        if not ok:
            raise RuntimeError("Failed to load user secret key from disk")
        self._user_sk = user_sk

        company_sk, ok = DeserializePrivateKey(str(_COMPANY_SK_FILE), BINARY)
        if not ok:
            raise RuntimeError("Failed to load company secret key from disk")
        self._company_sk = company_sk

        print("[OpenFHE] Keys loaded successfully", flush=True)

    # Crypto operations
    def serialize_crypto_context(self) -> str:
        return _serialize_to_b64(self.cc)

    def serialize_eval_mult_keys(self) -> str:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            path = tmp.name

        try:
            if not self.cc.SerializeEvalMultKey(path, BINARY):
                raise RuntimeError("OpenFHE failed to serialize EvalMult keys")
            data = Path(path).read_bytes()
            return _b64encode(data)
        finally:
            Path(path).unlink(missing_ok=True)

    def encrypt_scalar(self, value: float) -> str:
        plaintext  = self.cc.MakeCKKSPackedPlaintext([float(value)])
        ciphertext = self.cc.Encrypt(self.joint_public_key, plaintext)
        return _serialize_to_b64(ciphertext)

    def user_partial_decrypt_scalar(self, ciphertext_b64: str) -> str:
        ciphertext = _deserialize_ciphertext(ciphertext_b64)
        partials = self.cc.MultipartyDecryptLead([ciphertext], self._user_sk)
        return _serialize_to_b64(partials[0])

    def company_partial_decrypt_scalar(self, ciphertext_b64: str) -> str:
        ciphertext = _deserialize_ciphertext(ciphertext_b64)
        partials = self.cc.MultipartyDecryptMain([ciphertext], self._company_sk)
        return _serialize_to_b64(partials[0])

    def company_fuse_scalar(
        self,
        user_partial_b64: str,
        company_partial_b64: str,
    ) -> float:
        user_partial    = _deserialize_ciphertext(user_partial_b64)
        company_partial = _deserialize_ciphertext(company_partial_b64)

        plaintext = self.cc.MultipartyDecryptFusion([user_partial, company_partial])
        plaintext.SetLength(1)
        return float(plaintext.GetRealPackedValue()[0])
