from fastapi import HTTPException, status

from .repository import CompanyRepository
from .schemas import (
    JoinCompanyRequest,
    SaveEncryptedHomeRequest,
    SaveLatestLocationRequest,
    SubmitLocationStatusRequest,
)

repository = CompanyRepository()

class ClientCompanyService:
    def get_my_companies(self, current_user: dict) -> dict:
        companies = repository.get_user_companies(current_user["id"])
        return {"companies": companies}

    def join_company(self, request: JoinCompanyRequest, current_user: dict) -> dict:
        company = repository.get_company(request.company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")

        repository.join_company(
            company_id=request.company_id,
            user_id=current_user["id"],
        )

        return {
            "message": "Joined company successfully",
            "company_id": request.company_id,
        }

    def save_latest_location(self, request: SaveLatestLocationRequest, current_user: dict) -> dict:
        company = repository.get_company(request.company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")

        if not repository.is_employee_of_company(
            company_id=request.company_id,
            user_id=current_user["id"],
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Current user is not assigned to this company",
            )

        repository.save_latest_location_input(
            user_id=current_user["id"],
            data=request.model_dump(),
        )

        repository.clear_location_status(
            user_id=current_user["id"],
            company_id=request.company_id,
        )

        return {
            "message": "Latest location data saved for later company verification",
            "company_id": request.company_id,
            "user_id": current_user["id"],
        }

    def save_encrypted_home(self, request: SaveEncryptedHomeRequest, current_user: dict) -> dict:
        repository.save_encrypted_home(
            user_id=current_user["id"],
            data=request.model_dump(),
        )

        return {"message": "Encrypted home location saved successfully"}

    def submit_status(self, request: SubmitLocationStatusRequest, current_user: dict) -> dict:
        company = repository.get_company(request.company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")

        repository.submit_status(
            user_id=current_user["id"],
            data=request.model_dump(),
        )

        return {"message": "Location compliance status submitted successfully"}

    def get_my_location_status(self, company_id: int, current_user: dict) -> dict:
        company = repository.get_company(company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")

        if not repository.is_employee_of_company(company_id, current_user["id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Current user is not assigned to this company",
            )

        status_row = repository.get_user_location_status(
            user_id=current_user["id"],
            company_id=company_id,
        )

        if status_row is None:
            return {
                "company_id": company_id,
                "in_country": None,
                "at_home": None,
                "at_office": None,
                "last_updated": None,
                "pending": True,
            }

        return {
            "company_id": company_id,
            "in_country": status_row["in_country"],
            "at_home": status_row["at_home"],
            "at_office": status_row["at_office"],
            "last_updated": status_row["last_updated"],
            "pending": False,
        }

    def get_compliance_job_status(self, job_id: int, current_user: dict) -> dict:
        job = repository.get_compliance_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Compliance job not found")

        is_admin = repository.is_company_admin(
            company_id=job["company_id"],
            user_id=current_user["id"],
        )

        is_owner = int(job["user_id"]) == int(current_user["id"])

        if not is_admin and not is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to view this compliance job",
            )

        return {
            "job_id": job["id"],
            "status": job["status"],
            "encrypted_home_margin": job["encrypted_home_margin"],
            "encrypted_office_margin": job["encrypted_office_margin"],
            "encrypted_country_north_margin": job["encrypted_country_north_margin"],
            "encrypted_country_south_margin": job["encrypted_country_south_margin"],
            "encrypted_country_east_margin": job["encrypted_country_east_margin"],
            "encrypted_country_west_margin": job["encrypted_country_west_margin"],
            "user_partial_home_margin": job["user_partial_home_margin"],
            "user_partial_office_margin": job["user_partial_office_margin"],
            "user_partial_country_north_margin": job["user_partial_country_north_margin"],
            "user_partial_country_south_margin": job["user_partial_country_south_margin"],
            "user_partial_country_east_margin": job["user_partial_country_east_margin"],
            "user_partial_country_west_margin": job["user_partial_country_west_margin"],
            "final_at_home": job["final_at_home"],
            "final_at_office": job["final_at_office"],
            "final_in_country": job["final_in_country"],
        }
