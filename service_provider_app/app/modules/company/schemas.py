# service_provider_app/app/modules/company/schemas.py
from typing import Any

from pydantic import BaseModel, Field


class ComplianceEvaluationRequest(BaseModel):
    metadata: dict[str, Any] = Field(default_factory=dict)

    encrypted_current_lat: str
    encrypted_current_lon: str

    encrypted_home_lat: str
    encrypted_home_lon: str
    encrypted_home_radius: str

    encrypted_office_lat: str
    encrypted_office_lon: str
    encrypted_office_radius: str

    encrypted_country_north: str
    encrypted_country_south: str
    encrypted_country_east: str
    encrypted_country_west: str


class ComplianceEvaluationResponse(BaseModel):
    encrypted_home_margin: str
    encrypted_office_margin: str
    encrypted_country_north_margin: str
    encrypted_country_south_margin: str
    encrypted_country_east_margin: str
    encrypted_country_west_margin: str