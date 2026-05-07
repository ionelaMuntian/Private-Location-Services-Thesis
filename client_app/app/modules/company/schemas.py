from typing import List

from pydantic import BaseModel, Field


class CreateCompanyRequest(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    allowed_country: str = Field(..., min_length=2, max_length=100)
    office_name: str
    office_lat_m: float
    office_lon_m: float
    office_radius_m: float = 300.0


class CompanyResponse(BaseModel):
    id: int
    name: str
    allowed_country: str
    office_name: str
    office_lat_m: float
    office_lon_m: float
    office_radius_m: float


class JoinCompanyRequest(BaseModel):
    company_id: int


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
    last_updated: str | None = None


class CompanyUsersStatusResponse(BaseModel):
    company_id: int
    company_name: str
    users: List[UserLocationStatusItem]