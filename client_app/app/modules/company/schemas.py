from typing import List

from pydantic import BaseModel, Field


class CreateCompanyRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    allowed_country: str = Field(..., min_length=2, max_length=100)

    office_name: str
    office_lat_m: float
    office_lon_m: float
    office_radius_m: float = 300.0

    country_north_m: float | None = None
    country_south_m: float | None = None
    country_east_m: float | None = None
    country_west_m: float | None = None

    encrypted_office_lat_m: str | None = None
    encrypted_office_lon_m: str | None = None
    encrypted_office_radius_m: str | None = None
    encrypted_country_policy: str | None = None


class CompanyResponse(BaseModel):
    id: int
    name: str
    allowed_country: str
    office_name: str
    office_lat_m: float
    office_lon_m: float
    office_radius_m: float
    country_north_m: float | None = None
    country_south_m: float | None = None
    country_east_m: float | None = None
    country_west_m: float | None = None

class AdminCompaniesResponse(BaseModel):
    companies: List[CompanyResponse]


class MyCompaniesResponse(BaseModel):
    companies: List[CompanyResponse]


class JoinCompanyRequest(BaseModel):
    company_id: int


class AddEmployeeRequest(BaseModel):
    company_id: int
    user_id: int

class SaveLatestLocationRequest(BaseModel):
    company_id: int

    current_lat_m: float
    current_lon_m: float

    home_lat_m: float
    home_lon_m: float
    home_radius_m: float = 500.0


class SaveLatestLocationResponse(BaseModel):
    message: str
    company_id: int
    user_id: int


class SaveEncryptedHomeRequest(BaseModel):
    encrypted_home_lat_m: str
    encrypted_home_lon_m: str
    home_radius_m: float = 500.0


class SubmitLocationStatusRequest(BaseModel):
    company_id: int
    in_country: bool
    at_home: bool
    at_office: bool


class UserLocationStatusItem(BaseModel):
    user_id: int
    username: str
    email: str
    in_country: bool | None = None
    at_home: bool | None = None
    at_office: bool | None = None
    plaintext_in_country: bool | None = None
    plaintext_at_home: bool | None = None
    plaintext_at_office: bool | None = None
    last_updated: str | None = None

class CompanyUsersStatusResponse(BaseModel):
    company_id: int
    company_name: str
    users: List[UserLocationStatusItem]


class ComplianceJobResponse(BaseModel):
    job_id: int
    status: str


class RunComplianceCheckResponse(BaseModel):
    job_id: int
    status: str
    user_id: int
    username: str | None = None
    final_at_home: bool | None = None
    final_at_office: bool | None = None
    final_in_country: bool | None = None
    plaintext_at_home: bool | None = None
    plaintext_at_office: bool | None = None
    plaintext_in_country: bool | None = None


class MyLocationStatusResponse(BaseModel):
    company_id: int
    in_country: bool | None = None
    at_home: bool | None = None
    at_office: bool | None = None
    last_updated: str | None = None
    pending: bool = False


class ComplianceJobStatusResponse(BaseModel):
    job_id: int
    status: str

    encrypted_home_margin: str | None = None
    encrypted_office_margin: str | None = None
    encrypted_country_north_margin: str | None = None
    encrypted_country_south_margin: str | None = None
    encrypted_country_east_margin: str | None = None
    encrypted_country_west_margin: str | None = None

    user_partial_home_margin: str | None = None
    user_partial_office_margin: str | None = None
    user_partial_country_north_margin: str | None = None
    user_partial_country_south_margin: str | None = None
    user_partial_country_east_margin: str | None = None
    user_partial_country_west_margin: str | None = None

    final_at_home: bool | None = None
    final_at_office: bool | None = None
    final_in_country: bool | None = None