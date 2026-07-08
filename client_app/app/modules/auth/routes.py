# Purpose: it defines the endpoints and dispatches the received tasks to the corresponding services

from fastapi import APIRouter, Depends, HTTPException, status

from .dependencies import get_current_user
from .schemas import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserListResponse,
    UserResponse,
)
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


@router.get("/users", response_model=UserListResponse)
def list_users(current_user: dict = Depends(get_current_user)):
    if current_user["username"] != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admin can list users.",
        )

    return service.list_users()