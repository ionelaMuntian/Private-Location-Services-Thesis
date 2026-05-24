from pydantic import BaseModel, Field


class LoginPairFeatures(BaseModel):
    distance_km: float = Field(ge=0)
    speed_kmh: float = Field(ge=0)
    time_delta_h: float = Field(ge=0)
    same_country: int = Field(ge=0, le=1)
    same_city: int = Field(ge=0, le=1)
    same_browser: int = Field(ge=0, le=1)
    same_os: int = Field(ge=0, le=1)
    same_device: int = Field(ge=0, le=1)
    hour_of_day: int = Field(ge=0, le=23)
    is_weekend: int = Field(ge=0, le=1)


class AnomalyPredictRequest(BaseModel):
    features: LoginPairFeatures


class SchemeTiming(BaseModel):
    prediction: int          # 0 = normal, 1 = attack IP
    inference_ms: float


class AnomalyPredictResponse(BaseModel):
    plaintext: SchemeTiming
    fhe_simulate: SchemeTiming
    fhe_execute: SchemeTiming | None = None  # None when models not loaded
