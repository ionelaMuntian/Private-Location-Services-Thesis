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

# Fixed batch size for all categories.  Next power of 2 above the largest
# category in the UI (bank=122).  Using one fixed N avoids OpenFHE's global
# eval-mult key registry conflicts when multiple N-value contexts coexist.
N_SS = 128

# STD128 needs more levels for the CKKS→FHEW conversion polynomial than TOY.
# Server uses 4 levels (mul×2, mul×scale, mul×keep_mask); EvalMinSchemeSwitching
# needs ~35 for 128 slots with STD128.  Total = 39 → use 40 with buffer.
_SS_DEPTH = 52


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def _b64decode(data: str) -> bytes:
    return base64.b64decode(data.encode("utf-8"))


def _serialize_to_b64(obj: Any) -> str:
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        path = tmp.name
    try:
        if not SerializeToFile(path, obj, BINARY):
            raise RuntimeError("OpenFHE SS: failed to serialize object.")
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


def _get_toy_param():
    try:
        return openfhe.BINFHE_PARAMSET.TOY
    except AttributeError:
        return getattr(openfhe, "TOY", 0)


def _get_std128_param():
    try:
        return openfhe.BINFHE_PARAMSET.STD128
    except AttributeError:
        return getattr(openfhe, "STD128", 2)


class OpenFHESSClientRuntime:
    """
    CKKS + FHEW scheme-switching runtime for nearest-POI argmin.

    Uses a fixed batch size N_SS=128 for all categories.  The server fetches all
    real candidates for a category and pads the remaining slots with large dummy
    distances so the argmin always lands on a real POI.  The client restricts the
    winner search to the first len(candidates) slots of the decrypted one-hot vector.
    """

    def __init__(self) -> None:
        self.n = N_SS
        self.cc, self.keys = self._setup()

    def _setup(self):
        SchSwchParams = getattr(openfhe, "SchSwchParams", None)
        if SchSwchParams is None:
            raise RuntimeError(
                "openfhe.SchSwchParams not found — openfhe-python >= 1.5.0 required."
            )

        HEStd_NotSet = _get_hestd_not_set()
        STD128 = _get_std128_param()

        print(f"[OpenFHE SS] Setting up: n={self.n}, depth={_SS_DEPTH}, FHEW=STD128", flush=True)

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

    def serialize_crypto_context(self) -> str:
        return _serialize_to_b64(self.cc)

    def serialize_public_key(self) -> str:
        return _serialize_to_b64(self.keys.publicKey)

    def serialize_eval_mult_keys(self) -> str:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            path = tmp.name
        try:
            if not self.cc.SerializeEvalMultKey(path, BINARY):
                raise RuntimeError("OpenFHE SS: failed to serialize EvalMult keys.")
            return _b64encode(Path(path).read_bytes())
        finally:
            Path(path).unlink(missing_ok=True)

    def encrypt_broadcast(self, value: float) -> str:
        pt = self.cc.MakeCKKSPackedPlaintext([float(value)] * self.n)
        ct = self.cc.Encrypt(self.keys.publicKey, pt)
        return _serialize_to_b64(ct)

    def decrypt_argmin_via_ss(self, dist2_ct_b64: str, actual_n: int) -> int:
        """
        Runs EvalMinSchemeSwitching on the encrypted dist² ciphertext, then
        decrypts the one-hot argmin and restricts the winner search to the first
        actual_n slots (the real candidates; remaining slots are padding).
        """
        path = _write_b64_to_temp_file(dist2_ct_b64)
        try:
            ct, ok = DeserializeCiphertext(path, BINARY)
            if not ok:
                raise RuntimeError("OpenFHE SS: failed to deserialize dist² ciphertext.")
        finally:
            Path(path).unlink(missing_ok=True)

        print(
            f"[OpenFHE SS] EvalMinSchemeSwitching (n={self.n}, actual_candidates={actual_n})...",
            flush=True,
        )
        result = self.cc.EvalMinSchemeSwitching(
            ct, self.keys.publicKey, self.n, self.n
        )
        argmin_ct = result[1]

        pt = self.cc.Decrypt(argmin_ct, self.keys.secretKey)
        pt.SetLength(self.n)
        values = list(pt.GetRealPackedValue())[: self.n]

        if not values:
            raise ValueError("OpenFHE SS: empty argmin result.")

        # Restrict winner search to real candidates only (padding slots have large distances)
        real_values = values[:actual_n]
        print(
            f"[OpenFHE SS] Argmin one-hot (first {actual_n}): {[f'{v:.4f}' for v in real_values]}",
            flush=True,
        )
        winner_idx = max(range(len(real_values)), key=lambda i: abs(real_values[i]))
        print(f"[OpenFHE SS] Winner: slot {winner_idx}", flush=True)
        return winner_idx
