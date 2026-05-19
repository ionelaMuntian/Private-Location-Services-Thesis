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

N_SS_CANDIDATES = 16

# EvalMinSchemeSwitching needs 9+3+1+log2(16)=17 levels on a fresh ciphertext.
# The dist² pre-processing (dy², dx², scaling) consumes ~4 levels before SS is called.
# Total depth must cover both: 17 (SS) + 4 (dist²) = 21.
_SS_DEPTH = 21


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


class OpenFHESSClientRuntime:
    """
    CKKS + FHEW scheme-switching runtime for server-side nearest-POI argmin.

    The client encrypts query coordinates under CKKS and uploads evaluation keys
    (including scheme-switching keys) to the service provider.  The server
    computes encrypted squared distances, then runs EvalMinSchemeSwitching to
    find the argmin entirely on the server side.  The argmin one-hot ciphertext
    is returned to the client for decryption.

    The server never sees the plaintext query coordinates.
    The client decrypts only the winner index, not all distances.
    """

    n: int = N_SS_CANDIDATES

    def __init__(self) -> None:
        self.cc, self.keys = self._setup()

    # ------------------------------------------------------------------
    # Context + key setup
    # ------------------------------------------------------------------

    def _setup(self):
        SchSwchParams = getattr(openfhe, "SchSwchParams", None)
        if SchSwchParams is None:
            raise RuntimeError(
                "openfhe.SchSwchParams not found — openfhe-python >= 1.5.0 required."
            )

        HEStd_NotSet = _get_hestd_not_set()
        TOY = _get_toy_param()

        params = CCParamsCKKSRNS()
        params.SetMultiplicativeDepth(_SS_DEPTH)
        params.SetScalingModSize(52)
        params.SetFirstModSize(60)
        params.SetScalingTechnique(FLEXIBLEAUTO)
        params.SetBatchSize(self.n)
        params.SetNumLargeDigits(3)
        params.SetKeySwitchTechnique(HYBRID)
        params.SetSecurityLevel(HEStd_NotSet)
        params.SetRingDim(1 << 14)  # 16384; required when HEStd_NotSet is used; keeps SS keys < 400 MB

        cc = GenCryptoContext(params)
        cc.Enable(PKESchemeFeature.PKE)
        cc.Enable(PKESchemeFeature.KEYSWITCH)
        cc.Enable(PKESchemeFeature.LEVELEDSHE)
        cc.Enable(PKESchemeFeature.ADVANCEDSHE)
        cc.Enable(PKESchemeFeature.SCHEMESWITCH)
        cc.Enable(PKESchemeFeature.FHE)

        keys = cc.KeyGen()
        cc.EvalMultKeyGen(keys.secretKey)

        # Scheme-switching parameters
        ss_params = SchSwchParams()
        ss_params.SetSecurityLevelCKKS(HEStd_NotSet)
        ss_params.SetSecurityLevelFHEW(TOY)
        ss_params.SetNumSlotsCKKS(self.n)
        ss_params.SetNumValues(self.n)
        ss_params.SetComputeArgmin(True)
        ss_params.SetOneHotEncoding(True)

        # EvalSchemeSwitchingSetup returns the LWE private key directly (v1.5.1 API)
        lwe_sk = cc.EvalSchemeSwitchingSetup(ss_params)

        # Get the embedded BinFHE context and generate bootstrapping keys
        bfhcc = cc.GetBinCCForSchemeSwitch()
        bfhcc.BTKeyGen(lwe_sk)

        # Generate CKKS scheme-switching evaluation keys
        cc.EvalSchemeSwitchingKeyGen(keys, lwe_sk)

        # Precompute linear-transform matrices for CKKS→FHEW step
        cc.EvalCKKStoFHEWPrecompute()

        return cc, keys

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

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

    def serialize_eval_automorphism_keys(self) -> str:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            path = tmp.name
        try:
            if not self.cc.SerializeEvalAutomorphismKey(path, BINARY):
                raise RuntimeError("OpenFHE SS: failed to serialize EvalAutomorphism keys.")
            return _b64encode(Path(path).read_bytes())
        finally:
            Path(path).unlink(missing_ok=True)

    # ------------------------------------------------------------------
    # Encryption
    # ------------------------------------------------------------------

    def encrypt_broadcast(self, value: float) -> str:
        """Encrypts one scalar broadcast into all n slots: [v, v, ..., v]."""
        pt = self.cc.MakeCKKSPackedPlaintext([float(value)] * self.n)
        ct = self.cc.Encrypt(self.keys.publicKey, pt)
        return _serialize_to_b64(ct)

    # ------------------------------------------------------------------
    # Decryption of server-side argmin result
    # ------------------------------------------------------------------

    def decrypt_argmin_via_ss(self, dist2_ct_b64: str) -> int:
        """
        Applies EvalMinSchemeSwitching locally on the encrypted dist² ciphertext
        returned by the server, then decrypts only the one-hot argmin result.

        The full key set (eval-mult, eval-automorphism, BinFHE BTKeys, LKSK) is
        available on the client because it generated them.  The server does the
        CKKS distance computation; the client does the scheme-switching argmin.
        Privacy is preserved: the client learns only the winner index, not all distances.
        """
        path = _write_b64_to_temp_file(dist2_ct_b64)
        try:
            ct, ok = DeserializeCiphertext(path, BINARY)
            if not ok:
                raise RuntimeError("OpenFHE SS: failed to deserialize dist² ciphertext.")
        finally:
            Path(path).unlink(missing_ok=True)

        print(
            "[OpenFHE SS] Running EvalMinSchemeSwitching locally (CKKS→FHEW scheme-switching argmin)...",
            flush=True,
        )
        # Returns [ct_min, ct_argmin]; ct_argmin is one-hot with ~1.0 at the winner slot.
        result = self.cc.EvalMinSchemeSwitching(ct, self.keys.publicKey, self.n, self.n)
        argmin_ct = result[1]

        pt = self.cc.Decrypt(argmin_ct, self.keys.secretKey)
        pt.SetLength(self.n)
        values = list(pt.GetRealPackedValue())[: self.n]

        if not values:
            raise ValueError("OpenFHE SS: empty argmin result.")

        print(
            f"[OpenFHE SS] Argmin one-hot slots: {[f'{v:.4f}' for v in values]}",
            flush=True,
        )
        winner_idx = max(range(len(values)), key=lambda i: abs(values[i]))
        print(f"[OpenFHE SS] Scheme-switching argmin winner: slot {winner_idx}", flush=True)
        return winner_idx
