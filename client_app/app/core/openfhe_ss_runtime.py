
import base64
import tempfile
from pathlib import Path
from typing import Any

import openfhe
from openfhe import (
    BINARY,
    CCParamsCKKSRNS,
    DeserializeCiphertext,
    GenCryptoContext,
    PKESchemeFeature,
    SerializeToFile,
)

FLEXIBLEAUTO = getattr(openfhe, "FLEXIBLEAUTO", openfhe.ScalingTechnique.FLEXIBLEAUTO)
HYBRID = getattr(openfhe, "HYBRID", openfhe.KeySwitchTechnique.HYBRID)

_SS_DEPTH = 52


def next_power_of_2(n: int) -> int:
    if n <= 1:
        return 1
    return 1 << (n - 1).bit_length()

def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def _b64decode(data: str) -> bytes:
    return base64.b64decode(data.encode("utf-8"))


def _serialize_to_b64(obj: Any) -> str:
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        path = tmp.name
    try:
        if not SerializeToFile(path, obj, BINARY):
            raise RuntimeError("OpenFHE SS: failed to serialize object")
        return _b64encode(Path(path).read_bytes())
    finally:
        Path(path).unlink(missing_ok=True)


def _write_b64_to_temp_file(payload_b64: str) -> str:
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(_b64decode(payload_b64))
        return tmp.name


def _get_hestd_not_set():
    try:
        return openfhe.SecurityLevel.HEStd_NotSet
    except AttributeError:
        return getattr(openfhe, "HEStd_NotSet", 0)


def _get_std128_param():
    try:
        return openfhe.BINFHE_PARAMSET.STD128
    except AttributeError:
        return getattr(openfhe, "STD128", 2)


class OpenFHESSClientRuntime:
    def __init__(self, n: int) -> None:
        if n != next_power_of_2(n):
            raise ValueError(f"OpenFHE SS: batch size n={n} must be a power of 2")
        self.n = n
        self.cc, self.keys = self._setup()

    def _setup(self):
        SchSwchParams = getattr(openfhe, "SchSwchParams", None)
        if SchSwchParams is None:
            raise RuntimeError(
                "openfhe.SchSwchParams not found"
            )

        HEStd_NotSet = _get_hestd_not_set()
        STD128 = _get_std128_param()

        params = CCParamsCKKSRNS()
        params.SetMultiplicativeDepth(_SS_DEPTH)
        params.SetScalingModSize(59)
        params.SetFirstModSize(60)
        params.SetScalingTechnique(FLEXIBLEAUTO)
        params.SetBatchSize(self.n)
        params.SetNumLargeDigits(3)
        params.SetKeySwitchTechnique(HYBRID)
        params.SetSecurityLevel(HEStd_NotSet)
        params.SetRingDim(1 << 14)

        cc = GenCryptoContext(params)
        cc.Enable(PKESchemeFeature.PKE)
        cc.Enable(PKESchemeFeature.KEYSWITCH)
        cc.Enable(PKESchemeFeature.LEVELEDSHE)
        cc.Enable(PKESchemeFeature.ADVANCEDSHE)
        cc.Enable(PKESchemeFeature.SCHEMESWITCH)
        cc.Enable(PKESchemeFeature.FHE)

        keys = cc.KeyGen()
        cc.EvalMultKeyGen(keys.secretKey)

        ss_params = SchSwchParams()
        ss_params.SetSecurityLevelCKKS(HEStd_NotSet)
        ss_params.SetSecurityLevelFHEW(STD128)
        ss_params.SetNumSlotsCKKS(self.n)
        ss_params.SetNumValues(self.n)
        ss_params.SetComputeArgmin(True)
        ss_params.SetOneHotEncoding(True)
        lwe_sk = cc.EvalSchemeSwitchingSetup(ss_params)

        bfhcc = cc.GetBinCCForSchemeSwitch()
        bfhcc.BTKeyGen(lwe_sk)

        cc.EvalSchemeSwitchingKeyGen(keys, lwe_sk)

        cc.EvalCKKStoFHEWPrecompute()

        return cc, keys

    def serialize_crypto_context_to_file(self) -> str:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            path = tmp.name
        if not SerializeToFile(path, self.cc, BINARY):
            Path(path).unlink(missing_ok=True)
            raise RuntimeError("OpenFHE SS: failed to serialize crypto context to file")
        return path

    def serialize_public_key_to_file(self) -> str:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            path = tmp.name
        if not SerializeToFile(path, self.keys.publicKey, BINARY):
            Path(path).unlink(missing_ok=True)
            raise RuntimeError("OpenFHE SS: failed to serialize public key to file")
        return path

    def serialize_eval_mult_keys_to_file(self) -> str:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            path = tmp.name
        if not self.cc.SerializeEvalMultKey(path, BINARY):
            Path(path).unlink(missing_ok=True)
            raise RuntimeError("OpenFHE SS: failed to serialize EvalMult keys to file")
        return path

    # Encryption
    def encrypt_broadcast(self, value: float) -> str:
        pt = self.cc.MakeCKKSPackedPlaintext([float(value)] * self.n)
        ct = self.cc.Encrypt(self.keys.publicKey, pt)
        return _serialize_to_b64(ct)

    # Client-side: EvalMinSchemeSwitching
    def eval_min_scheme_switching(self, dist_ct_b64: str, actual_n: int) -> int:
        path = _write_b64_to_temp_file(dist_ct_b64)
        try:
            ct, ok = DeserializeCiphertext(path, BINARY)
            if not ok:
                raise RuntimeError("OpenFHE SS: failed to deserialize distance ciphertext")
        finally:
            Path(path).unlink(missing_ok=True)

        result = self.cc.EvalMinSchemeSwitching(ct, self.keys.publicKey, self.n, self.n)

        if isinstance(result, (list, tuple)) and len(result) >= 2:
            argmin_ct = result[1]
        else:
            argmin_ct = result

        pt = self.cc.Decrypt(argmin_ct, self.keys.secretKey)
        pt.SetLength(self.n)
        values = list(pt.GetRealPackedValue())[:actual_n]

        if not values:
            raise ValueError("OpenFHE SS: empty argmin result")

        winner_idx = max(range(len(values)), key=lambda i: abs(values[i]))
        return winner_idx
