import base64
import tempfile
from pathlib import Path
from typing import Any

from openfhe import *


def _b64decode(data: str) -> bytes:
    return base64.b64decode(data.encode("utf-8"))


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def _write_b64_to_temp_file(payload_b64: str) -> str:
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        tmp.write(_b64decode(payload_b64))
        return tmp.name


def _serialize_to_b64(obj: Any) -> str:
    with tempfile.NamedTemporaryFile(delete=False) as tmp:
        path = tmp.name

    try:
        if not SerializeToFile(path, obj, BINARY):
            raise RuntimeError(f"OpenFHE failed to serialize object to {path}")
        return _b64encode(Path(path).read_bytes())
    finally:
        Path(path).unlink(missing_ok=True)


def load_crypto_context(context_b64: str):
    path = _write_b64_to_temp_file(context_b64)

    try:
        cc, ok = DeserializeCryptoContext(path, BINARY)
        if not ok:
            raise RuntimeError("OpenFHE failed to deserialize CryptoContext.")
        return cc
    finally:
        Path(path).unlink(missing_ok=True)


def load_ciphertext(ciphertext_b64: str):
    path = _write_b64_to_temp_file(ciphertext_b64)

    try:
        ciphertext, ok = DeserializeCiphertext(path, BINARY)
        if not ok:
            raise RuntimeError("OpenFHE failed to deserialize ciphertext.")
        return ciphertext
    finally:
        Path(path).unlink(missing_ok=True)


def load_eval_mult_keys(cc, eval_mult_keys_b64: str) -> None:
    path = _write_b64_to_temp_file(eval_mult_keys_b64)

    try:
        try:
            if not cc.DeserializeEvalMultKey(path, BINARY):
                raise RuntimeError("OpenFHE failed to deserialize EvalMult keys.")
        except RuntimeError as exc:
            # The Python binding's cc.ClearEvalMultKeys() only clears keys for
            # cc's own (empty) keyTag, not the joint-public-key tag already in
            # the global store from a previous request.  When the same client
            # sends the same persisted keys on every call, the global store
            # already contains the correct keys — safe to reuse them.
            if "there is a key vector for the given keyTag" not in str(exc):
                raise
    finally:
        Path(path).unlink(missing_ok=True)


def dump_ciphertext(ciphertext) -> str:
    return _serialize_to_b64(ciphertext)