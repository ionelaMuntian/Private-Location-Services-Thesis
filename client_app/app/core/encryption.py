# client_app/app/core/encryption.py
import base64
import json
from typing import Any

import tenseal as ts

from .config import settings

def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def _b64decode(data: str) -> bytes:
    return base64.b64decode(data.encode("utf-8"))


class CKKSContextManager:
    @staticmethod
    def create_full_context() -> ts.Context:
        context = ts.context(
            ts.SCHEME_TYPE.CKKS,
            poly_modulus_degree=settings.ckks_poly_modulus_degree,
            coeff_mod_bit_sizes=settings.ckks_coeff_mod_bit_sizes_list,
        )
        context.generate_galois_keys()
        context.generate_relin_keys()
        context.global_scale = 2 ** settings.ckks_global_scale_bits
        return context

    @staticmethod
    def serialize_public_context(full_context: ts.Context) -> str:
        public_context = full_context.copy()
        public_context.make_context_public()
        return _b64encode(public_context.serialize())

    @staticmethod
    def serialize_secret_context(full_context: ts.Context) -> str:
        return _b64encode(full_context.serialize(save_secret_key=True))

    @staticmethod
    def load_public_context(serialized_public_context: str) -> ts.Context:
        return ts.context_from(_b64decode(serialized_public_context))

    @staticmethod
    def load_secret_context(serialized_secret_context: str) -> ts.Context:
        return ts.context_from(_b64decode(serialized_secret_context))


class BFVContextManager:
    @staticmethod
    def create_full_context() -> ts.Context:
        context = ts.context(
            ts.SCHEME_TYPE.BFV,
            poly_modulus_degree=settings.bfv_poly_modulus_degree,
            plain_modulus=settings.bfv_plain_modulus,
        )
        context.generate_galois_keys()
        context.generate_relin_keys()
        return context

    @staticmethod
    def serialize_public_context(full_context: ts.Context) -> str:
        public_context = full_context.copy()
        public_context.make_context_public()
        return _b64encode(public_context.serialize())

    @staticmethod
    def serialize_secret_context(full_context: ts.Context) -> str:
        return _b64encode(full_context.serialize(save_secret_key=True))

    @staticmethod
    def load_public_context(serialized_public_context: str) -> ts.Context:
        return ts.context_from(_b64decode(serialized_public_context))

    @staticmethod
    def load_secret_context(serialized_secret_context: str) -> ts.Context:
        return ts.context_from(_b64decode(serialized_secret_context))


def serialize_ckks_vector(vector: ts.CKKSVector) -> str:
    return _b64encode(vector.serialize())


def deserialize_ckks_vector(context: ts.Context, payload: str) -> ts.CKKSVector:
    return ts.ckks_vector_from(context, _b64decode(payload))


def serialize_bfv_vector(vector: ts.BFVVector) -> str:
    return _b64encode(vector.serialize())


def deserialize_bfv_vector(context: ts.Context, payload: str) -> ts.BFVVector:
    return ts.bfv_vector_from(context, _b64decode(payload))


def dump_json(data: dict[str, Any]) -> str:
    return json.dumps(data, ensure_ascii=False)


def load_json(data: str) -> dict[str, Any]:
    return json.loads(data)