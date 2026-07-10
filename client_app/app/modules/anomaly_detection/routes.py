from fastapi import APIRouter, Depends

from ..auth.dependencies import get_current_user
from .schemas import InferRequest, InferResponse, SamplesResponse
from .service import AnomalyDetectionClientService

router = APIRouter()
service = AnomalyDetectionClientService()

@router.get("/samples", response_model=SamplesResponse)
async def list_samples(
    current_user: dict = Depends(get_current_user),
):
    return await service.list_samples()

@router.post("/infer", response_model=InferResponse)
async def infer(
    request: InferRequest,
    current_user: dict = Depends(get_current_user),
):
    return await service.infer(request.sample_id, request.mode)
