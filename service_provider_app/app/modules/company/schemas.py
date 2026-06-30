from typing import Any

from pydantic import BaseModel, Field


class ComplianceEvaluationRequest(BaseModel):
    metadata: dict[str, Any] = Field(default_factory=dict)

    encrypted_current_lat: str
    encrypted_current_lon: str

    encrypted_home_north: str
    encrypted_home_south: str
    encrypted_home_east: str
    encrypted_home_west: str

    encrypted_office_north: str
    encrypted_office_south: str
    encrypted_office_east: str
    encrypted_office_west: str

    encrypted_country_north: str
    encrypted_country_south: str
    encrypted_country_east: str
    encrypted_country_west: str


class ComplianceEvaluationResponse(BaseModel):
    encrypted_home_north_margin: str
    encrypted_home_south_margin: str
    encrypted_home_east_margin: str
    encrypted_home_west_margin: str
    encrypted_office_north_margin: str
    encrypted_office_south_margin: str
    encrypted_office_east_margin: str
    encrypted_office_west_margin: str
    encrypted_country_north_margin: str
    encrypted_country_south_margin: str
    encrypted_country_east_margin: str
    encrypted_country_west_margin: str
