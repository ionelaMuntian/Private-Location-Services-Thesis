from fastapi import APIRouter, HTTPException

from .schemas import AnomalyPredictRequest, AnomalyPredictResponse
from .service import AnomalyDetectionService

router = APIRouter()
service = AnomalyDetectionService()


@router.get("/health")
async def health():
    return {"ready": service.ready()}


@router.post("/predict", response_model=AnomalyPredictResponse)
async def predict(request: AnomalyPredictRequest):
    if not service.ready():
        raise HTTPException(
            status_code=503,
            detail="Anomaly detection models not loaded. Run the training notebook first.",
        )
    return await service.predict(request)
