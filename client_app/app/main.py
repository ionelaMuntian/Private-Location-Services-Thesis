from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .core.config import settings
from .modules.anomaly_detection.routes import router as anomaly_detection_router
from .modules.auth.routes import router as auth_router
from .modules.auth.service import AuthService
from .modules.company.client_routes import router as company_client_router
from .modules.company.company_routes import router as company_admin_router
from .modules.company.company_service import CompanyAdminService
from .modules.poi_search.routes import router as poi_router

app = FastAPI(title=settings.app_name)

auth_service = AuthService()
company_admin_service = CompanyAdminService()


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": f"{type(exc).__name__}: {exc}"},
    )

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup_event() -> None:
    auth_service.initialize_auth_storage()
    company_admin_service.initialize_storage()


app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(poi_router, prefix="/client/poi", tags=["poi-search"])
app.include_router(
    company_client_router,
    prefix="/client/company",
    tags=["company-location-compliance"],
)
app.include_router(
    company_admin_router,
    prefix="/client/company",
    tags=["company-location-compliance"],
)
app.include_router(
    anomaly_detection_router,
    prefix="/client/anomaly-detection",
    tags=["anomaly-detection"],
)


@app.get("/")
def root():
    return {"message": settings.app_name}