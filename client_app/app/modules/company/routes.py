from fastapi import APIRouter, Depends

from ..auth.dependencies import get_current_user
from .schemas import (
    CompanyResponse,
    CompanyUsersStatusResponse,
    CreateCompanyRequest,
    JoinCompanyRequest,
    SaveEncryptedHomeRequest,
    SubmitLocationStatusRequest,
)
from .service import CompanyService

router = APIRouter()
service = CompanyService()


@router.post("/companies", response_model=CompanyResponse)
def create_company(
    request: CreateCompanyRequest,
    current_user: dict = Depends(get_current_user),
):
    return service.create_company(request, current_user)


@router.post("/companies/join")
def join_company(
    request: JoinCompanyRequest,
    current_user: dict = Depends(get_current_user),
):
    return service.join_company(request, current_user)


@router.post("/home-location")
def save_encrypted_home_location(
    request: SaveEncryptedHomeRequest,
    current_user: dict = Depends(get_current_user),
):
    return service.save_encrypted_home(request, current_user)


@router.post("/status")
def submit_location_status(
    request: SubmitLocationStatusRequest,
    current_user: dict = Depends(get_current_user),
):
    return service.submit_status(request, current_user)


@router.get("/companies/{company_id}/users-status", response_model=CompanyUsersStatusResponse)
def get_company_users_status(
    company_id: int,
    current_user: dict = Depends(get_current_user),
):
    return service.get_users_status(company_id, current_user)