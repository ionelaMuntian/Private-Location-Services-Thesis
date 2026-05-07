from fastapi import HTTPException, status

from .repository import CompanyRepository
from .schemas import (
    CreateCompanyRequest,
    JoinCompanyRequest,
    SaveEncryptedHomeRequest,
    SubmitLocationStatusRequest,
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

    def join_company(self, request: JoinCompanyRequest, current_user: dict) -> dict:
        company = repository.get_company(request.company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found.")

        repository.join_company(company_id=request.company_id, user_id=current_user["id"])

        return {"message": "Joined company successfully.", "company_id": request.company_id}

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