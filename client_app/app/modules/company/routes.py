from fastapi import APIRouter, Depends, Query

from ..auth.dependencies import get_current_user
from .schemas import (
    AddEmployeeRequest,
    AdminCompaniesResponse,
    CompanyResponse,
    CompanyUsersStatusResponse,
    ComplianceJobStatusResponse,
    CreateCompanyRequest,
    JoinCompanyRequest,
    MyCompaniesResponse,
    MyLocationStatusResponse,
    RunComplianceCheckResponse,
    SaveEncryptedHomeRequest,
    SaveLatestLocationRequest,
    SaveLatestLocationResponse,
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

@router.put("/companies/{company_id}", response_model=CompanyResponse)
def update_company(
    company_id: int,
    request: CreateCompanyRequest,
    current_user: dict = Depends(get_current_user),
):
    return service.update_company(company_id, request, current_user)


@router.delete("/companies/{company_id}")
def delete_company(
    company_id: int,
    current_user: dict = Depends(get_current_user),
):
    return service.delete_company(company_id, current_user)


@router.get("/admin/companies", response_model=AdminCompaniesResponse)
def get_my_admin_companies(
    current_user: dict = Depends(get_current_user),
):
    return service.get_my_admin_companies(current_user)


@router.get("/my-companies", response_model=MyCompaniesResponse)
def get_my_companies(
    current_user: dict = Depends(get_current_user),
):
    return service.get_my_companies(current_user)


@router.post("/employees")
def add_employee(
    request: AddEmployeeRequest,
    current_user: dict = Depends(get_current_user),
):
    return service.add_employee(request, current_user)


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


@router.get("/companies/{company_id}/users-status", response_model=CompanyUsersStatusResponse)
def get_company_users_status(
    company_id: int,
    current_user: dict = Depends(get_current_user),
):
    return service.get_users_status(company_id, current_user)


@router.post(
    "/companies/{company_id}/employees/{user_id}/run-compliance-check",
    response_model=RunComplianceCheckResponse,
)
async def run_employee_compliance_check(
    company_id: int,
    user_id: int,
    current_user: dict = Depends(get_current_user),
):
    return await service.run_employee_compliance_check(
        company_id=company_id,
        employee_user_id=user_id,
        current_user=current_user,
    )


@router.get("/compliance-jobs/{job_id}", response_model=ComplianceJobStatusResponse)
def get_compliance_job_status(
    job_id: int,
    current_user: dict = Depends(get_current_user),
):
    return service.get_compliance_job_status(job_id, current_user)


@router.post("/compliance-jobs/{job_id}/complete-demo")
def complete_compliance_job_demo(
    job_id: int,
    final_at_home: bool = Query(...),
    final_at_office: bool = Query(...),
    final_in_country: bool = Query(...),
    current_user: dict = Depends(get_current_user),
):
    return service.complete_compliance_job_demo(
        job_id=job_id,
        final_at_home=final_at_home,
        final_at_office=final_at_office,
        final_in_country=final_in_country,
        current_user=current_user,
    )