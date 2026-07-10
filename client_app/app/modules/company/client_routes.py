from fastapi import APIRouter, Depends

from ..auth.dependencies import get_current_user
from .client_service import ClientCompanyService
from .schemas import (
    ComplianceJobStatusResponse,
    JoinCompanyRequest,
    MyCompaniesResponse,
    MyLocationStatusResponse,
    SaveEncryptedHomeRequest,
    SaveLatestLocationRequest,
    SaveLatestLocationResponse,
    SubmitLocationStatusRequest,
)

router = APIRouter()
service = ClientCompanyService()


@router.get("/my-companies", response_model=MyCompaniesResponse)
def get_my_companies(
    current_user: dict = Depends(get_current_user),
):
    return service.get_my_companies(current_user)


@router.post("/companies/join")
def join_company(
    request: JoinCompanyRequest,
    current_user: dict = Depends(get_current_user),
):
    return service.join_company(request, current_user)


@router.post("/latest-location", response_model=SaveLatestLocationResponse)
def save_latest_location(
    request: SaveLatestLocationRequest,
    current_user: dict = Depends(get_current_user),
):
    return service.save_latest_location(request, current_user)


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


@router.get("/companies/{company_id}/my-status", response_model=MyLocationStatusResponse)
def get_my_location_status(
    company_id: int,
    current_user: dict = Depends(get_current_user),
):
    return service.get_my_location_status(company_id, current_user)


@router.get("/compliance-jobs/{job_id}", response_model=ComplianceJobStatusResponse)
def get_compliance_job_status(
    job_id: int,
    current_user: dict = Depends(get_current_user),
):
    return service.get_compliance_job_status(job_id, current_user)
