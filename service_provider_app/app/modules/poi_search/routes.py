from fastapi import APIRouter

from .schemas import (
    CategoryListResponse,
    ConcreteEvaluationRequest,
    ConcreteEvaluationResponse,
    OpenFHESSEvaluateRequest,
    OpenFHESSEvaluateResponse,
    OpenFHESSUploadKeysRequest,
    OpenFHESSUploadKeysResponse,
    ServiceProviderNearestKRequest,
    ServiceProviderNearestKResponse,
)
from .service import PoiSearchServiceProviderService

router = APIRouter()
service = PoiSearchServiceProviderService()


@router.post("/nearest-k", response_model=ServiceProviderNearestKResponse)
def nearest_k_by_category(request: ServiceProviderNearestKRequest):
    return service.nearest_k_by_category(request)


@router.get("/categories", response_model=CategoryListResponse)
def list_categories():
    return service.list_categories()


@router.post("/concrete/evaluate", response_model=ConcreteEvaluationResponse)
def concrete_evaluate(request: ConcreteEvaluationRequest):
    return service.concrete_evaluate(request)


@router.post("/openfhe-ss/upload-keys", response_model=OpenFHESSUploadKeysResponse)
def openfhe_ss_upload_keys(request: OpenFHESSUploadKeysRequest):
    return service.openfhe_ss_upload_keys(request)


@router.post("/openfhe-ss/evaluate", response_model=OpenFHESSEvaluateResponse)
def openfhe_ss_evaluate(request: OpenFHESSEvaluateRequest):
    return service.openfhe_ss_evaluate(request)

