# client_app/app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .modules.auth.routes import router as auth_router
from .modules.auth.service import AuthService
from .modules.poi_search.routes import router as poi_router

app = FastAPI(title=settings.app_name)

auth_service = AuthService()

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


app.include_router(auth_router, prefix="/auth", tags=["auth"])
app.include_router(poi_router, prefix="/client/poi", tags=["poi-search"])

@app.get("/")
def root():
    return {"message": settings.app_name}