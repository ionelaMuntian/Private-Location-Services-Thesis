# client_app/app/modules/company/service.py
from fastapi import HTTPException, status

from .repository import CompanyRepository
from .schemas import (
    AddEmployeeRequest,
    CreateCompanyRequest,
    JoinCompanyRequest,
    SaveEncryptedHomeRequest,
    ShareEncryptedLocationRequest,
    SubmitCompanyPartialDecryptionRequest,
    SubmitLocationStatusRequest,
    SubmitUserPartialDecryptionRequest,
)

repository = CompanyRepository()


class CompanyService:
    def initialize_storage(self) -> None:
        repository.initialize()

    def create_company(self, request: CreateCompanyRequest, current_user: dict) -> dict:
        return repository.create_company(
            data=request.model_dump(),
            admin_user_id=current_user["id"],
        )

    def get_my_admin_companies(self, current_user: dict) -> dict:
        companies = repository.get_admin_companies(current_user["id"])
        return {"companies": companies}

    def add_employee(self, request: AddEmployeeRequest, current_user: dict) -> dict:
        company = repository.get_company(request.company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found.")

        if not repository.is_company_admin(request.company_id, current_user["id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only company administrators can add employees.",
            )

        repository.add_employee_to_company(
            company_id=request.company_id,
            user_id=request.user_id,
        )

        return {
            "message": "Employee added successfully.",
            "company_id": request.company_id,
            "user_id": request.user_id,
        }

    def join_company(self, request: JoinCompanyRequest, current_user: dict) -> dict:
        company = repository.get_company(request.company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found.")

        repository.join_company(
            company_id=request.company_id,
            user_id=current_user["id"],
        )

        return {
            "message": "Joined company successfully.",
            "company_id": request.company_id,
        }

    def save_encrypted_home(
        self,
        request: SaveEncryptedHomeRequest,
        current_user: dict,
    ) -> dict:
        repository.save_encrypted_home(
            user_id=current_user["id"],
            data=request.model_dump(),
        )

        return {"message": "Encrypted home location saved successfully."}

    def submit_status(
        self,
        request: SubmitLocationStatusRequest,
        current_user: dict,
    ) -> dict:
        company = repository.get_company(request.company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found.")

        repository.submit_status(
            user_id=current_user["id"],
            data=request.model_dump(),
        )

        return {"message": "Location compliance status submitted successfully."}

    def get_users_status(self, company_id: int, current_user: dict) -> dict:
        company = repository.get_company(company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found.")

        if not repository.is_company_admin(company_id, current_user["id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only company administrators can view employee statuses.",
            )

        users = repository.get_users_status(company_id)

        return {
            "company_id": company["id"],
            "company_name": company["name"],
            "users": users,
        }

    def share_encrypted_location(
        self,
        request: ShareEncryptedLocationRequest,
        current_user: dict,
    ) -> dict:
        company = repository.get_company(request.company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found.")

        # If the user shares location for this company, ensure they are linked
        # to that company.
        repository.join_company(
            company_id=request.company_id,
            user_id=current_user["id"],
        )

        job = repository.create_compliance_job(
            user_id=current_user["id"],
            data=request.model_dump(),
            company=company,
        )

        return {
            "job_id": job["id"],
            "status": job["status"],
        }

    def get_compliance_job_status(self, job_id: int, current_user: dict) -> dict:
        job = repository.get_compliance_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Compliance job not found.")

        is_admin = repository.is_company_admin(
            company_id=job["company_id"],
            user_id=current_user["id"],
        )

        is_owner = int(job["user_id"]) == int(current_user["id"])

        if not is_admin and not is_owner:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not allowed to view this compliance job.",
            )

        return {
            "job_id": job["id"],
            "status": job["status"],
            "final_at_home": job["final_at_home"],
            "final_at_office": job["final_at_office"],
            "final_in_country": job["final_in_country"],
        }

    def submit_user_partial_decryption(
        self,
        request: SubmitUserPartialDecryptionRequest,
        current_user: dict,
    ) -> dict:
        job = repository.get_compliance_job(request.job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Compliance job not found.")

        if int(job["user_id"]) != int(current_user["id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Only the employee assigned to this job can submit the user "
                    "partial decryption."
                ),
            )

        result = repository.submit_user_partial_decryption(
            user_id=current_user["id"],
            data=request.model_dump(),
        )

        if result is None:
            raise HTTPException(
                status_code=404,
                detail="Compliance job not found or not owned by current user.",
            )

        return {
            "job_id": result["id"],
            "status": result["status"],
        }

    def submit_company_partial_decryption(
        self,
        request: SubmitCompanyPartialDecryptionRequest,
        current_user: dict,
    ) -> dict:
        job = repository.get_compliance_job(request.job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Compliance job not found.")

        if not repository.is_company_admin(job["company_id"], current_user["id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only company administrators can submit company partial decryption.",
            )

        result = repository.submit_company_partial_decryption(
            data=request.model_dump(),
        )

        if result is None:
            raise HTTPException(
                status_code=404,
                detail="Compliance job not found.",
            )

        return {
            "job_id": result["id"],
            "status": result["status"],
        }

    def get_my_companies(self, current_user: dict) -> dict:
        companies = repository.get_user_companies(current_user["id"])
        return {"companies": companies}

    def complete_compliance_job_demo(
        self,
        job_id: int,
        final_at_home: bool,
        final_at_office: bool,
        final_in_country: bool,
        current_user: dict,
    ) -> dict:
        """
        Temporary helper endpoint for UI testing before the OpenFHE multiparty
        combine step is integrated.

        Later this should be replaced by:
          combine_decryption_shares(job_id)
        """
        job = repository.get_compliance_job(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Compliance job not found.")

        if not repository.is_company_admin(job["company_id"], current_user["id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only company administrators can complete the job.",
            )

        result = repository.mark_compliance_job_completed(
            job_id=job_id,
            final_at_home=final_at_home,
            final_at_office=final_at_office,
            final_in_country=final_in_country,
        )

        if result is None:
            raise HTTPException(status_code=404, detail="Compliance job not found.")

        repository.submit_status(
            user_id=job["user_id"],
            data={
                "company_id": job["company_id"],
                "at_home": final_at_home,
                "at_office": final_at_office,
                "in_country": final_in_country,
            },
        )

        return {
            "job_id": result["id"],
            "status": result["status"],
            "final_at_home": result["final_at_home"],
            "final_at_office": result["final_at_office"],
            "final_in_country": result["final_in_country"],
        }