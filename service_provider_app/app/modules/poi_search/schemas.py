# service_provider_app/app/modules/poi_search/schemas.py
from typing import Any, List, Literal

from pydantic import BaseModel, Field, model_validator


SingleSchemeType = Literal["plaintext", "ckks", "bfv", "concrete"]
SchemeType = Literal["plaintext", "ckks", "bfv", "concrete"]


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
    # metadata must NOT contain plaintext coordinates for HE schemes.
    # Valid keys: public_context, query_encoding, distance_metric,
    #             top_k_on_client, requested_k, bfv_scale, evaluation_keys.
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
        if self.scheme in {"ckks", "bfv", "concrete"} and self.encrypted_query is None:
            raise ValueError(f"encrypted_query is required when scheme='{self.scheme}'")
        # Extra guard: reject any request that sneaks plaintext coordinates into
        # the encrypted_query metadata for HE schemes.
        if self.scheme in {"ckks", "bfv", "concrete"} and self.encrypted_query is not None:
            forbidden = {"query_latitude_m", "query_longitude_m"}
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
    """
    The server returns all POIs in the requested category.
    No user location is included — the server must not learn where the user is.
    """
    category: str
    k: int = Field(..., gt=0, le=200)
    # latitude_m and longitude_m have been intentionally removed.


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
    public_args_b64: str


class ConcreteEvaluationRequest(BaseModel):
    evaluation_keys_b64: str
    requested_k: int
    items: List[ConcreteEvaluationItem]


class ConcreteEvaluationResultItem(BaseModel):
    id: int
    name: str
    category: str
    latitude: float
    longitude: float
    encrypted_distance: str


class ConcreteEvaluationResponse(BaseModel):
    scheme: SingleSchemeType
    encrypted_results: List[ConcreteEvaluationResultItem]
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


class PoiNameSearchItem(BaseModel):
    id: int
    name: str
    category: str
    latitude: float
    longitude: float


class PoiNameSearchResponse(BaseModel):
    query: str
    count: int
    results: List[PoiNameSearchItem]