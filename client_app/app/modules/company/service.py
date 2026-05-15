# client_app/app/modules/company/service.py

from fastapi import HTTPException, status

from ...core.openfhe_multiparty_instance import openfhe_multiparty_runtime
from ...infrastructure.grpc_client import post_to_service_provider
from .repository import CompanyRepository
from .schemas import (
    AddEmployeeRequest,
    CreateCompanyRequest,
    JoinCompanyRequest,
    SaveEncryptedHomeRequest,
    SaveLatestLocationRequest,
    SubmitLocationStatusRequest,
)

repository = CompanyRepository()

EPSILON = 1e-3


def _leq_zero(value: float) -> bool:
    return value <= EPSILON


def _geq_zero(value: float) -> bool:
    return value >= -EPSILON


class CompanyService:
    def initialize_storage(self) -> None:
        repository.initialize()

    def create_company(self, request: CreateCompanyRequest, current_user: dict) -> dict:
        data = request.model_dump()

        data["encrypted_office_lat_m"] = openfhe_multiparty_runtime.encrypt_scalar(
            request.office_lat_m
        )
        data["encrypted_office_lon_m"] = openfhe_multiparty_runtime.encrypt_scalar(
            request.office_lon_m
        )
        data["encrypted_office_radius_m"] = openfhe_multiparty_runtime.encrypt_scalar(
            request.office_radius_m
        )

        data["encrypted_country_north_m"] = openfhe_multiparty_runtime.encrypt_scalar(
            request.country_north_m or 0.0
        )
        data["encrypted_country_south_m"] = openfhe_multiparty_runtime.encrypt_scalar(
            request.country_south_m or 0.0
        )
        data["encrypted_country_east_m"] = openfhe_multiparty_runtime.encrypt_scalar(
            request.country_east_m or 0.0
        )
        data["encrypted_country_west_m"] = openfhe_multiparty_runtime.encrypt_scalar(
            request.country_west_m or 0.0
        )

        return repository.create_company(
            data=data,
            admin_user_id=current_user["id"],
        )

    def get_my_admin_companies(self, current_user: dict) -> dict:
        companies = repository.get_admin_companies(current_user["id"])
        return {"companies": companies}

    def get_my_companies(self, current_user: dict) -> dict:
        companies = repository.get_user_companies(current_user["id"])
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

    def save_latest_location(
        self,
        request: SaveLatestLocationRequest,
        current_user: dict,
    ) -> dict:
        company = repository.get_company(request.company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found.")

        if not repository.is_employee_of_company(
            company_id=request.company_id,
            user_id=current_user["id"],
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Current user is not assigned to this company.",
            )

        repository.save_latest_location_input(
            user_id=current_user["id"],
            data=request.model_dump(),
        )

        return {
            "message": "Latest location data saved for later company verification.",
            "company_id": request.company_id,
            "user_id": current_user["id"],
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

    async def run_employee_compliance_check(
        self,
        company_id: int,
        employee_user_id: int,
        current_user: dict,
    ) -> dict:
        company = repository.get_company(company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found.")

        if not repository.is_company_admin(company_id, current_user["id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only company administrators can run compliance checks.",
            )

        if not repository.is_employee_of_company(company_id, employee_user_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Selected user is not assigned to this company.",
            )

        location_input = repository.get_latest_location_input(
            company_id=company_id,
            user_id=employee_user_id,
        )

        if location_input is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    "No prepared location data exists for this employee. "
                    "The employee must first press Share / Update Location."
                ),
            )

        encrypted_current_lat = openfhe_multiparty_runtime.encrypt_scalar(
            location_input["current_lat_m"]
        )
        encrypted_current_lon = openfhe_multiparty_runtime.encrypt_scalar(
            location_input["current_lon_m"]
        )
        encrypted_home_lat = openfhe_multiparty_runtime.encrypt_scalar(
            location_input["home_lat_m"]
        )
        encrypted_home_lon = openfhe_multiparty_runtime.encrypt_scalar(
            location_input["home_lon_m"]
        )
        encrypted_home_radius = openfhe_multiparty_runtime.encrypt_scalar(
            location_input["home_radius_m"]
        )

        service_payload = {
            "metadata": {
                "crypto_context": openfhe_multiparty_runtime.serialize_crypto_context(),
                "eval_mult_keys": openfhe_multiparty_runtime.serialize_eval_mult_keys(),
            },
            "encrypted_current_lat": encrypted_current_lat,
            "encrypted_current_lon": encrypted_current_lon,
            "encrypted_home_lat": encrypted_home_lat,
            "encrypted_home_lon": encrypted_home_lon,
            "encrypted_home_radius": encrypted_home_radius,
            "encrypted_office_lat": company["encrypted_office_lat_m"],
            "encrypted_office_lon": company["encrypted_office_lon_m"],
            "encrypted_office_radius": company["encrypted_office_radius_m"],
            "encrypted_country_north": company["encrypted_country_north_m"],
            "encrypted_country_south": company["encrypted_country_south_m"],
            "encrypted_country_east": company["encrypted_country_east_m"],
            "encrypted_country_west": company["encrypted_country_west_m"],
        }

        encrypted_margins = await post_to_service_provider(
            "/service/company/compliance/evaluate",
            service_payload,
        )

        job = repository.create_compliance_job(
            user_id=employee_user_id,
            data={
                "company_id": company_id,
                "encrypted_current_lat": encrypted_current_lat,
                "encrypted_current_lon": encrypted_current_lon,
                "encrypted_home_lat": encrypted_home_lat,
                "encrypted_home_lon": encrypted_home_lon,
                "encrypted_home_radius": encrypted_home_radius,
                **encrypted_margins,
            },
            company=company,
        )

        job_id = int(job["id"])

        user_partials = {
            "user_partial_home_margin": openfhe_multiparty_runtime.user_partial_decrypt_scalar(
                encrypted_margins["encrypted_home_margin"]
            ),
            "user_partial_office_margin": openfhe_multiparty_runtime.user_partial_decrypt_scalar(
                encrypted_margins["encrypted_office_margin"]
            ),
            "user_partial_country_north_margin": openfhe_multiparty_runtime.user_partial_decrypt_scalar(
                encrypted_margins["encrypted_country_north_margin"]
            ),
            "user_partial_country_south_margin": openfhe_multiparty_runtime.user_partial_decrypt_scalar(
                encrypted_margins["encrypted_country_south_margin"]
            ),
            "user_partial_country_east_margin": openfhe_multiparty_runtime.user_partial_decrypt_scalar(
                encrypted_margins["encrypted_country_east_margin"]
            ),
            "user_partial_country_west_margin": openfhe_multiparty_runtime.user_partial_decrypt_scalar(
                encrypted_margins["encrypted_country_west_margin"]
            ),
        }

        repository.store_user_partials(
            job_id=job_id,
            user_id=employee_user_id,
            partials=user_partials,
        )

        company_partial_home = openfhe_multiparty_runtime.company_partial_decrypt_scalar(
            encrypted_margins["encrypted_home_margin"]
        )
        company_partial_office = openfhe_multiparty_runtime.company_partial_decrypt_scalar(
            encrypted_margins["encrypted_office_margin"]
        )
        company_partial_north = openfhe_multiparty_runtime.company_partial_decrypt_scalar(
            encrypted_margins["encrypted_country_north_margin"]
        )
        company_partial_south = openfhe_multiparty_runtime.company_partial_decrypt_scalar(
            encrypted_margins["encrypted_country_south_margin"]
        )
        company_partial_east = openfhe_multiparty_runtime.company_partial_decrypt_scalar(
            encrypted_margins["encrypted_country_east_margin"]
        )
        company_partial_west = openfhe_multiparty_runtime.company_partial_decrypt_scalar(
            encrypted_margins["encrypted_country_west_margin"]
        )

        home_margin = openfhe_multiparty_runtime.company_fuse_scalar(
            user_partials["user_partial_home_margin"],
            company_partial_home,
        )
        office_margin = openfhe_multiparty_runtime.company_fuse_scalar(
            user_partials["user_partial_office_margin"],
            company_partial_office,
        )
        north_margin = openfhe_multiparty_runtime.company_fuse_scalar(
            user_partials["user_partial_country_north_margin"],
            company_partial_north,
        )
        south_margin = openfhe_multiparty_runtime.company_fuse_scalar(
            user_partials["user_partial_country_south_margin"],
            company_partial_south,
        )
        east_margin = openfhe_multiparty_runtime.company_fuse_scalar(
            user_partials["user_partial_country_east_margin"],
            company_partial_east,
        )
        west_margin = openfhe_multiparty_runtime.company_fuse_scalar(
            user_partials["user_partial_country_west_margin"],
            company_partial_west,
        )

        final_at_home = _leq_zero(home_margin)
        final_at_office = _leq_zero(office_margin)
        final_in_country = (
            _geq_zero(north_margin)
            and _geq_zero(south_margin)
            and _geq_zero(east_margin)
            and _geq_zero(west_margin)
        )

        result = repository.store_company_fusion_result(
            job_id=job_id,
            company_partials={
                "company_partial_home_margin": company_partial_home,
                "company_partial_office_margin": company_partial_office,
                "company_partial_country_north_margin": company_partial_north,
                "company_partial_country_south_margin": company_partial_south,
                "company_partial_country_east_margin": company_partial_east,
                "company_partial_country_west_margin": company_partial_west,
            },
            margins={
                "home_margin": home_margin,
                "office_margin": office_margin,
                "country_north_margin": north_margin,
                "country_south_margin": south_margin,
                "country_east_margin": east_margin,
                "country_west_margin": west_margin,
            },
            final_at_home=final_at_home,
            final_at_office=final_at_office,
            final_in_country=final_in_country,
        )

        repository.submit_status(
            user_id=employee_user_id,
            data={
                "company_id": company_id,
                "at_home": final_at_home,
                "at_office": final_at_office,
                "in_country": final_in_country,
            },
        )

        employee = repository.get_user_summary(employee_user_id)

        return {
            "job_id": result["id"],
            "status": result["status"],
            "user_id": employee_user_id,
            "username": employee["username"] if employee else None,
            "final_at_home": result["final_at_home"],
            "final_at_office": result["final_at_office"],
            "final_in_country": result["final_in_country"],
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

    def complete_compliance_job_demo(
        self,
        job_id: int,
        final_at_home: bool,
        final_at_office: bool,
        final_in_country: bool,
        current_user: dict,
    ) -> dict:
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