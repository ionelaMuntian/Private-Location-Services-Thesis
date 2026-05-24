# service_provider_app/app/modules/poi_search/schemas.py

from typing import Any, List, Literal

from pydantic import BaseModel, Field, model_validator


SingleSchemeType = Literal["plaintext", "ckks", "concrete", "openfhe_ss"]
SchemeType = Literal["plaintext", "ckks", "concrete", "openfhe_ss"]


class ServerTimingMetrics(BaseModel):
    candidate_selection_ms: float | None = None
    computation_ms: float | None = None
    evaluation_ms: float | None = None
    total_ms: float


class WorkloadMetrics(BaseModel):
    candidate_count: int | None = None
    returned_count: int
    k: int
    category: str


class MetricsEnvelope(BaseModel):
    server: ServerTimingMetrics
    workload: WorkloadMetrics


class EncryptedLocationPayload(BaseModel):
    payload: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlaintextLocationPayload(BaseModel):
    latitude_m: float
    longitude_m: float


class ServiceProviderNearestKRequest(BaseModel):
    category: str
    k: int = Field(..., gt=0, le=200)
    scheme: SchemeType
    encrypted_query: EncryptedLocationPayload | None = None
    plaintext_query: PlaintextLocationPayload | None = None

    @model_validator(mode="after")
    def validate_payload_for_scheme(self):
        if self.scheme == "plaintext" and self.plaintext_query is None:
            raise ValueError("plaintext_query is required when scheme='plaintext'")

        if (
            self.scheme in {"ckks", "concrete"}
            and self.encrypted_query is None
        ):
            raise ValueError(
                f"encrypted_query is required when scheme='{self.scheme}'"
            )

        if (
            self.scheme in {"ckks", "concrete"}
            and self.encrypted_query is not None
        ):
            forbidden = {
                "query_latitude_m",
                "query_longitude_m",
                "latitude_m",
                "longitude_m",
            }

            leaked = forbidden & set(self.encrypted_query.metadata.keys())

            if leaked:
                raise ValueError(
                    f"Plaintext coordinates must not be included in encrypted_query.metadata "
                    f"for scheme='{self.scheme}'. Found: {leaked}"
                )

        return self


class PoiResult(BaseModel):
    id: int
    name: str
    category: str
    latitude: float
    longitude: float
    distance_km: float


class EncryptedPoiResult(BaseModel):
    id: int
    name: str
    category: str
    latitude: float
    longitude: float
    encrypted_distance: str


class CandidatePoiItem(BaseModel):
    id: int
    name: str
    category: str
    latitude: float
    longitude: float
    lat_m: float
    lon_m: float


class ConcreteCandidatesRequest(BaseModel):
    category: str
    k: int = Field(..., gt=0, le=200)
    n_candidates: int = Field(2, ge=1, le=20)


class ConcreteCandidatesResponse(BaseModel):
    category: str
    k: int
    candidates: List[CandidatePoiItem]
    metrics: MetricsEnvelope


class ConcreteEvaluationItem(BaseModel):
    id: int
    name: str
    category: str
    latitude: float
    longitude: float

    # Clear POI coordinates after quantization and origin-shifting.
    # These are public candidate coordinates, not user coordinates.
    px: int
    py: int


class ConcreteEvaluationRequest(BaseModel):
    # New optimized mode:
    # key_id references evaluation keys previously uploaded by streaming gRPC.
    key_id: str | None = None

    # Backward-compatible fallback:
    # direct evaluation keys can still be sent, but this is not recommended
    # because Concrete evaluation keys are extremely large.
    evaluation_keys_b64: str | None = None

    encrypted_user_coords_b64: str
    requested_k: int = Field(..., gt=0, le=200)
    items: List[ConcreteEvaluationItem]

    @model_validator(mode="after")
    def validate_key_source(self):
        if not self.key_id and not self.evaluation_keys_b64:
            raise ValueError(
                "Concrete evaluation requires either key_id or evaluation_keys_b64."
            )

        return self


class ConcreteEvaluationResultItem(BaseModel):
    id: int
    name: str
    category: str
    latitude: float
    longitude: float
    encrypted_distance: str


class ConcreteSortedResult(BaseModel):
    # Encrypted outputs of the Concrete find-minimum circuit.
    # The server does not decrypt these values.
    best_id: str
    best_dist2: str


class ConcreteEvaluationResponse(BaseModel):
    scheme: SingleSchemeType
    encrypted_best_result: ConcreteSortedResult | None = None
    metadata: dict[str, Any]
    metrics: MetricsEnvelope


class ServiceProviderNearestKResponse(BaseModel):
    scheme: SingleSchemeType
    results: List[PoiResult] | None = None
    encrypted_results: List[EncryptedPoiResult] | None = None
    metadata: dict[str, Any] | None = None
    metrics: MetricsEnvelope


class CategoryListResponse(BaseModel):
    categories: List[str]



# ---------------------------------------------------------------------------
# OpenFHE Scheme-Switching schemas
# ---------------------------------------------------------------------------

class OpenFHESSUploadKeysRequest(BaseModel):
    crypto_context_b64: str
    public_key_b64: str
    eval_mult_keys_b64: str
    eval_automorphism_keys_b64: str = ""
    n_candidates: int = Field(128, ge=1, le=256)


class OpenFHESSUploadKeysResponse(BaseModel):
    key_id: str
    expires_in_seconds: int


class OpenFHESSEvaluateRequest(BaseModel):
    key_id: str
    encrypted_qy: str
    encrypted_qx: str
    category: str
    n_candidates: int = Field(128, ge=1, le=256)


class OpenFHESSEvaluateResponse(BaseModel):
    scheme: SingleSchemeType
    dist2_ct_b64: str
    candidates: List[dict]
    metrics: MetricsEnvelope