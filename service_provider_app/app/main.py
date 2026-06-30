from fastapi import FastAPI

from .core.config import settings
from .modules.poi_search.routes import router as poi_search_router
app = FastAPI(title=settings.app_name)

app.include_router(poi_search_router, prefix="/service/poi", tags=["Service POI"])
