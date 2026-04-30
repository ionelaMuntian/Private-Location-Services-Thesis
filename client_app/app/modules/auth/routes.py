# client_app/app/modules/auth/routes.py
from fastapi import APIRouter, Depends

from .dependencies import get_current_user
from .schemas import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from .service import AuthService


router = APIRouter()
service = AuthService()


@router.post("/register", response_model=UserResponse)
def register(request: RegisterRequest):
    return service.register_user(
        username=request.username,
        email=request.email,
        password=request.password,
    )


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest):
    return service.login_user(
        username=request.username,
        password=request.password,
    )


@router.get("/me", response_model=UserResponse)
def me(current_user: dict = Depends(get_current_user)):
    return current_user