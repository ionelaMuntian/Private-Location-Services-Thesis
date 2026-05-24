# service_provider_app/app/main.py
from fastapi import FastAPI

from .core.config import settings
from .modules.poi_search.routes import router as poi_search_router
app = FastAPI(title=settings.app_name)

app.include_router(poi_search_router, prefix="/service/poi", tags=["Service POI"])
# anomaly_detection routes not yet implemented — enable after ml_model/schemas/routes are added
# from .modules.anomaly_detection.routes import router as anomaly_router
# app.include_router(anomaly_router, prefix="/service/anomaly-detection", tags=["Anomaly Detection"])