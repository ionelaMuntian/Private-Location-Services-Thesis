import base64

import tenseal as ts


def _b64encode(data: bytes) -> str:
    return base64.b64encode(data).decode("utf-8")


def _b64decode(data: str) -> bytes:
    return base64.b64decode(data.encode("utf-8"))


def load_public_context(serialized_public_context: str) -> ts.Context:
    return ts.context_from(_b64decode(serialized_public_context))


def load_ckks_vector(context: ts.Context, payload: str) -> ts.CKKSVector:
    return ts.ckks_vector_from(context, _b64decode(payload))


def dump_ckks_vector(vector: ts.CKKSVector) -> str:
    return _b64encode(vector.serialize())


def load_bfv_vector(context: ts.Context, payload: str) -> ts.BFVVector:
    return ts.bfv_vector_from(context, _b64decode(payload))


def dump_bfv_vector(vector: ts.BFVVector) -> str:
    return _b64encode(vector.serialize())