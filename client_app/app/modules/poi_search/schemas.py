# client_app/app/modules/poi_search/schemas.py
from typing import List, Literal, Union

from pydantic import BaseModel, Field


SingleSchemeType = Literal["plaintext", "ckks", "bfv", "concrete", "openfhe"]
SchemeType = Literal["plaintext", "ckks", "bfv", "concrete", "openfhe", "all"]

class ClientTimingMetrics(BaseModel):
    prepare_query_ms: float | None = None
    service_call_ms: float | None = None
    parse_response_ms: float | None = None
    candidate_fetch_ms: float | None = None
    build_public_args_ms: float | None = None
    evaluate_call_ms: float | None = None
    total_ms: float


class ServerTimingMetrics(BaseModel):
    candidate_selection_ms: float | None = None
    computation_ms: float | None = None
    evaluation_ms: float | None = None
    total_ms: float | None = None


class WorkloadMetrics(BaseModel):
    candidate_count: int | None = None
    returned_count: int
    k: int
    category: str


class MetricsEnvelope(BaseModel):
    client: ClientTimingMetrics
    server: ServerTimingMetrics | None = None
    workload: WorkloadMetrics


class NearestKClientRequest(BaseModel):
    category: str = Field(..., examples=["bank", "cafe", "supermarket"])
    k: int = Field(..., gt=0, le=200)
    latitude_m: float = Field(..., description="Projected metric latitude-like coordinate (EPSG:3857 Y)")
    longitude_m: float = Field(..., description="Projected metric longitude-like coordinate (EPSG:3857 X)")
    scheme: SchemeType = "plaintext"


class PoiItem(BaseModel):
    id: int
    name: str
    category: str
    latitude: float
    longitude: float
    distance_km: float


class NearestKClientResponse(BaseModel):
    scheme: SingleSchemeType
    category: str
    k: int
    results: List[PoiItem]
    metrics: MetricsEnvelope


class SchemeRunResponse(BaseModel):
    scheme: SingleSchemeType
    category: str
    k: int
    results: List[PoiItem]
    metrics: MetricsEnvelope


class AllSchemesComparisonResponse(BaseModel):
    mode: Literal["all"]
    category: str
    k: int
    runs: List[SchemeRunResponse]


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

NearestKResponseType = Union[NearestKClientResponse, AllSchemesComparisonResponse]