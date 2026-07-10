from pydantic import BaseModel


class PredictPlaintextRequest(BaseModel):
    sample_id: int


class FheEvaluateRequest(BaseModel):
    encrypted_query_b64: str
    evaluation_keys_b64: str
