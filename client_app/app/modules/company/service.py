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

# Tolerance for CKKS approximation noise when interpreting the sign of a margin.
# After COORD_SCALE=100 normalization, smallest radius² is (100m/100)² = 1.0,
# so 1e-3 is well below any meaningful margin value.
EPSILON = 1e-3
# CKKS approximation error grows with value magnitude. Dividing by COORD_SCALE
# keeps numbers small enough (~10^3 instead of ~10^6) so that after squaring
# (~10^6 instead of ~10^12) the noise stays well below any reasonable radius².
# All comparisons are scale-invariant (dividing both sides preserves the sign).
COORD_SCALE = 100.0


def _leq_zero(value: float) -> bool:
    return value <= EPSILON


def _geq_zero(value: float) -> bool:
    return value >= -EPSILON


def _compute_plaintext_compliance(location_input: dict, company: dict) -> dict:
    current_lat = float(location_input["current_lat_m"])
    current_lon = float(location_input["current_lon_m"])
    home_lat    = float(location_input["home_lat_m"])
    home_lon    = float(location_input["home_lon_m"])
    home_radius = float(location_input["home_radius_m"])

    office_lat    = float(company["office_lat_m"])
    office_lon    = float(company["office_lon_m"])
    office_radius = float(company["office_radius_m"])

    home_dist_sq   = (current_lat - home_lat) ** 2 + (current_lon - home_lon) ** 2
    office_dist_sq = (current_lat - office_lat) ** 2 + (current_lon - office_lon) ** 2

    plaintext_at_home   = home_dist_sq   <= home_radius ** 2
    plaintext_at_office = office_dist_sq <= office_radius ** 2

    north = company.get("country_north_m")
    south = company.get("country_south_m")
    east  = company.get("country_east_m")
    west  = company.get("country_west_m")

    if all(v is not None for v in [north, south, east, west]):
        plaintext_in_country = (
            south <= current_lat <= north
            and west <= current_lon <= east
        )
    else:
        plaintext_in_country = None

    return {
        "plaintext_at_home": plaintext_at_home,
        "plaintext_at_office": plaintext_at_office,
        "plaintext_in_country": plaintext_in_country,
    }


class CompanyService:
    def initialize_storage(self) -> None:
        repository.initialize()

    def create_company(self, request: CreateCompanyRequest, current_user: dict) -> dict:
        data = request.model_dump()

        data["encrypted_office_lat_m"] = openfhe_multiparty_runtime.encrypt_scalar(
            request.office_lat_m / COORD_SCALE
        )
        data["encrypted_office_lon_m"] = openfhe_multiparty_runtime.encrypt_scalar(
            request.office_lon_m / COORD_SCALE
        )
        data["encrypted_office_radius_m"] = openfhe_multiparty_runtime.encrypt_scalar(
            request.office_radius_m / COORD_SCALE
        )

        data["encrypted_country_north_m"] = openfhe_multiparty_runtime.encrypt_scalar(
            (request.country_north_m or 0.0) / COORD_SCALE
        )
        data["encrypted_country_south_m"] = openfhe_multiparty_runtime.encrypt_scalar(
            (request.country_south_m or 0.0) / COORD_SCALE
        )
        data["encrypted_country_east_m"] = openfhe_multiparty_runtime.encrypt_scalar(
            (request.country_east_m or 0.0) / COORD_SCALE
        )
        data["encrypted_country_west_m"] = openfhe_multiparty_runtime.encrypt_scalar(
            (request.country_west_m or 0.0) / COORD_SCALE
        )

        return repository.create_company(
            data=data,
            admin_user_id=current_user["id"],
        )

    def update_company(self, company_id: int, request: CreateCompanyRequest, current_user: dict) -> dict:
        if not repository.is_company_admin(company_id, current_user["id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only company administrators can update this company.",
            )

        data = request.model_dump()

        data["encrypted_office_lat_m"] = openfhe_multiparty_runtime.encrypt_scalar(
            request.office_lat_m / COORD_SCALE
        )
        data["encrypted_office_lon_m"] = openfhe_multiparty_runtime.encrypt_scalar(
            request.office_lon_m / COORD_SCALE
        )
        data["encrypted_office_radius_m"] = openfhe_multiparty_runtime.encrypt_scalar(
            request.office_radius_m / COORD_SCALE
        )
        data["encrypted_country_north_m"] = openfhe_multiparty_runtime.encrypt_scalar(
            (request.country_north_m or 0.0) / COORD_SCALE
        )
        data["encrypted_country_south_m"] = openfhe_multiparty_runtime.encrypt_scalar(
            (request.country_south_m or 0.0) / COORD_SCALE
        )
        data["encrypted_country_east_m"] = openfhe_multiparty_runtime.encrypt_scalar(
            (request.country_east_m or 0.0) / COORD_SCALE
        )
        data["encrypted_country_west_m"] = openfhe_multiparty_runtime.encrypt_scalar(
            (request.country_west_m or 0.0) / COORD_SCALE
        )

        result = repository.update_company(
            company_id=company_id,
            data=data,
            admin_user_id=current_user["id"],
        )

        if result is None:
            raise HTTPException(status_code=404, detail="Company not found.")

        return result

    def delete_company(self, company_id: int, current_user: dict) -> dict:
        if not repository.is_company_admin(company_id, current_user["id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only company administrators can delete this company.",
            )

        deleted = repository.delete_company(company_id, current_user["id"])
        if not deleted:
            raise HTTPException(status_code=404, detail="Company not found.")

        return {"message": "Company deleted successfully.", "company_id": company_id}

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

        # Reset status to pending so the employee's polling no longer shows
        # a stale result from the previous compliance check.
        repository.clear_location_status(
            user_id=current_user["id"],
            company_id=request.company_id,
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
            location_input["current_lat_m"] / COORD_SCALE
        )
        encrypted_current_lon = openfhe_multiparty_runtime.encrypt_scalar(
            location_input["current_lon_m"] / COORD_SCALE
        )
        encrypted_home_lat = openfhe_multiparty_runtime.encrypt_scalar(
            location_input["home_lat_m"] / COORD_SCALE
        )
        encrypted_home_lon = openfhe_multiparty_runtime.encrypt_scalar(
            location_input["home_lon_m"] / COORD_SCALE
        )
        encrypted_home_radius = openfhe_multiparty_runtime.encrypt_scalar(
            location_input["home_radius_m"] / COORD_SCALE
        )

        encrypted_office_lat = openfhe_multiparty_runtime.encrypt_scalar(
            company["office_lat_m"] / COORD_SCALE
        )
        encrypted_office_lon = openfhe_multiparty_runtime.encrypt_scalar(
            company["office_lon_m"] / COORD_SCALE
        )
        encrypted_office_radius = openfhe_multiparty_runtime.encrypt_scalar(
            company["office_radius_m"] / COORD_SCALE
        )
        encrypted_country_north = openfhe_multiparty_runtime.encrypt_scalar(
            (company["country_north_m"] or 0.0) / COORD_SCALE
        )
        encrypted_country_south = openfhe_multiparty_runtime.encrypt_scalar(
            (company["country_south_m"] or 0.0) / COORD_SCALE
        )
        encrypted_country_east = openfhe_multiparty_runtime.encrypt_scalar(
            (company["country_east_m"] or 0.0) / COORD_SCALE
        )
        encrypted_country_west = openfhe_multiparty_runtime.encrypt_scalar(
            (company["country_west_m"] or 0.0) / COORD_SCALE
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
            "encrypted_office_lat": encrypted_office_lat,
            "encrypted_office_lon": encrypted_office_lon,
            "encrypted_office_radius": encrypted_office_radius,
            "encrypted_country_north": encrypted_country_north,
            "encrypted_country_south": encrypted_country_south,
            "encrypted_country_east": encrypted_country_east,
            "encrypted_country_west": encrypted_country_west,
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

        plaintext = _compute_plaintext_compliance(location_input, company)

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
            plaintext_at_home=plaintext["plaintext_at_home"],
            plaintext_at_office=plaintext["plaintext_at_office"],
            plaintext_in_country=plaintext["plaintext_in_country"],
        )

        repository.submit_status(
            user_id=employee_user_id,
            data={
                "company_id": company_id,
                "at_home": final_at_home,
                "at_office": final_at_office,
                "in_country": final_in_country,
                "plaintext_at_home": plaintext["plaintext_at_home"],
                "plaintext_at_office": plaintext["plaintext_at_office"],
                "plaintext_in_country": plaintext["plaintext_in_country"],
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
            "plaintext_at_home": result["plaintext_at_home"],
            "plaintext_at_office": result["plaintext_at_office"],
            "plaintext_in_country": result["plaintext_in_country"],
        }

    def get_my_location_status(self, company_id: int, current_user: dict) -> dict:
        company = repository.get_company(company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found.")

        if not repository.is_employee_of_company(company_id, current_user["id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Current user is not assigned to this company.",
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