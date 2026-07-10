from typing import Literal

from pydantic import BaseModel


class SampleItem(BaseModel):
    id: int
    label: str
    true_label: int


class SamplesResponse(BaseModel):
    samples: list[SampleItem]


class InferRequest(BaseModel):
    sample_id: int
    mode: Literal["plaintext", "encrypted", "both"]


class PlaintextResult(BaseModel):
    probability: float
    prediction: int
    true_label: int
    latency_ms: float


class EncryptedResult(BaseModel):
    probability: float
    prediction: int
    true_label: int
    latency_ms: float


class InferResponse(BaseModel):
    plaintext: PlaintextResult | None = None
    encrypted: EncryptedResult | None = None
