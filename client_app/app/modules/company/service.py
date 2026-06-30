
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

    plaintext_at_home = (
        home_lat - home_radius <= current_lat <= home_lat + home_radius
        and home_lon - home_radius <= current_lon <= home_lon + home_radius
    )
    plaintext_at_office = (
        office_lat - office_radius <= current_lat <= office_lat + office_radius
        and office_lon - office_radius <= current_lon <= office_lon + office_radius
    )

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

        enc = openfhe_multiparty_runtime.encrypt_scalar

        encrypted_current_lat = enc(location_input["current_lat_m"] / COORD_SCALE)
        encrypted_current_lon = enc(location_input["current_lon_m"] / COORD_SCALE)

        home_lat_sc = location_input["home_lat_m"] / COORD_SCALE
        home_lon_sc = location_input["home_lon_m"] / COORD_SCALE
        home_r_sc = location_input["home_radius_m"] / COORD_SCALE

        encrypted_home_north = enc(home_lat_sc + home_r_sc)
        encrypted_home_south = enc(home_lat_sc - home_r_sc)
        encrypted_home_east  = enc(home_lon_sc + home_r_sc)
        encrypted_home_west  = enc(home_lon_sc - home_r_sc)

        encrypted_home_lat = enc(home_lat_sc)
        encrypted_home_lon = enc(home_lon_sc)
        encrypted_home_radius = enc(home_r_sc)

        office_lat_sc = company["office_lat_m"] / COORD_SCALE
        office_lon_sc = company["office_lon_m"] / COORD_SCALE
        office_r_sc = company["office_radius_m"] / COORD_SCALE

        encrypted_office_north = enc(office_lat_sc + office_r_sc)
        encrypted_office_south = enc(office_lat_sc - office_r_sc)
        encrypted_office_east  = enc(office_lon_sc + office_r_sc)
        encrypted_office_west  = enc(office_lon_sc - office_r_sc)

        encrypted_country_north = enc((company["country_north_m"] or 0.0) / COORD_SCALE)
        encrypted_country_south = enc((company["country_south_m"] or 0.0) / COORD_SCALE)
        encrypted_country_east  = enc((company["country_east_m"]  or 0.0) / COORD_SCALE)
        encrypted_country_west  = enc((company["country_west_m"]  or 0.0) / COORD_SCALE)

        service_payload = {
            "metadata": {
                "crypto_context": openfhe_multiparty_runtime.serialize_crypto_context(),
                "eval_mult_keys": openfhe_multiparty_runtime.serialize_eval_mult_keys(),
            },
            "encrypted_current_lat": encrypted_current_lat,
            "encrypted_current_lon": encrypted_current_lon,
            "encrypted_home_north":  encrypted_home_north,
            "encrypted_home_south":  encrypted_home_south,
            "encrypted_home_east":   encrypted_home_east,
            "encrypted_home_west":   encrypted_home_west,
            "encrypted_office_north": encrypted_office_north,
            "encrypted_office_south": encrypted_office_south,
            "encrypted_office_east":  encrypted_office_east,
            "encrypted_office_west":  encrypted_office_west,
            "encrypted_country_north": encrypted_country_north,
            "encrypted_country_south": encrypted_country_south,
            "encrypted_country_east":  encrypted_country_east,
            "encrypted_country_west":  encrypted_country_west,
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
                "encrypted_home_lat":    encrypted_home_lat,
                "encrypted_home_lon":    encrypted_home_lon,
                "encrypted_home_radius": encrypted_home_radius,
                # Store north margin as the representative home/office ciphertext.
                "encrypted_home_margin":   encrypted_margins["encrypted_home_north_margin"],
                "encrypted_office_margin": encrypted_margins["encrypted_office_north_margin"],
                "encrypted_country_north_margin": encrypted_margins["encrypted_country_north_margin"],
                "encrypted_country_south_margin": encrypted_margins["encrypted_country_south_margin"],
                "encrypted_country_east_margin":  encrypted_margins["encrypted_country_east_margin"],
                "encrypted_country_west_margin":  encrypted_margins["encrypted_country_west_margin"],
            },
            company=company,
        )

        job_id = int(job["id"])

        up = openfhe_multiparty_runtime.user_partial_decrypt_scalar
        cp = openfhe_multiparty_runtime.company_partial_decrypt_scalar
        fuse = openfhe_multiparty_runtime.company_fuse_scalar

        up_home_north = up(encrypted_margins["encrypted_home_north_margin"])
        up_home_south = up(encrypted_margins["encrypted_home_south_margin"])
        up_home_east  = up(encrypted_margins["encrypted_home_east_margin"])
        up_home_west  = up(encrypted_margins["encrypted_home_west_margin"])

        up_office_north = up(encrypted_margins["encrypted_office_north_margin"])
        up_office_south = up(encrypted_margins["encrypted_office_south_margin"])
        up_office_east = up(encrypted_margins["encrypted_office_east_margin"])
        up_office_west = up(encrypted_margins["encrypted_office_west_margin"])

        up_country_north = up(encrypted_margins["encrypted_country_north_margin"])
        up_country_south = up(encrypted_margins["encrypted_country_south_margin"])
        up_country_east = up(encrypted_margins["encrypted_country_east_margin"])
        up_country_west = up(encrypted_margins["encrypted_country_west_margin"])

        repository.store_user_partials(
            job_id=job_id,
            user_id=employee_user_id,
            partials={
                "user_partial_home_margin":              up_home_north,
                "user_partial_office_margin":            up_office_north,
                "user_partial_country_north_margin":     up_country_north,
                "user_partial_country_south_margin":     up_country_south,
                "user_partial_country_east_margin":      up_country_east,
                "user_partial_country_west_margin":      up_country_west,
            },
        )

        cp_home_north = cp(encrypted_margins["encrypted_home_north_margin"])
        cp_home_south = cp(encrypted_margins["encrypted_home_south_margin"])
        cp_home_east = cp(encrypted_margins["encrypted_home_east_margin"])
        cp_home_west = cp(encrypted_margins["encrypted_home_west_margin"])

        cp_office_north = cp(encrypted_margins["encrypted_office_north_margin"])
        cp_office_south = cp(encrypted_margins["encrypted_office_south_margin"])
        cp_office_east  = cp(encrypted_margins["encrypted_office_east_margin"])
        cp_office_west  = cp(encrypted_margins["encrypted_office_west_margin"])

        cp_country_north = cp(encrypted_margins["encrypted_country_north_margin"])
        cp_country_south = cp(encrypted_margins["encrypted_country_south_margin"])
        cp_country_east  = cp(encrypted_margins["encrypted_country_east_margin"])
        cp_country_west  = cp(encrypted_margins["encrypted_country_west_margin"])

        home_north_m = fuse(up_home_north, cp_home_north)
        home_south_m = fuse(up_home_south, cp_home_south)
        home_east_m  = fuse(up_home_east,  cp_home_east)
        home_west_m  = fuse(up_home_west,  cp_home_west)

        office_north_m = fuse(up_office_north, cp_office_north)
        office_south_m = fuse(up_office_south, cp_office_south)
        office_east_m  = fuse(up_office_east,  cp_office_east)
        office_west_m  = fuse(up_office_west,  cp_office_west)

        north_margin = fuse(up_country_north, cp_country_north)
        south_margin = fuse(up_country_south, cp_country_south)
        east_margin  = fuse(up_country_east,  cp_country_east)
        west_margin  = fuse(up_country_west,  cp_country_west)

        home_margin  = min(home_north_m, home_south_m, home_east_m, home_west_m)
        office_margin = min(office_north_m, office_south_m, office_east_m, office_west_m)

        print(
            f"[Compliance] home bbox mins: N={home_north_m:.3f} S={home_south_m:.3f} "
            f"E={home_east_m:.3f} W={home_west_m:.3f} → at_home={_geq_zero(home_margin)}",
            flush=True,
        )
        print(
            f"[Compliance] office bbox mins: N={office_north_m:.3f} S={office_south_m:.3f} "
            f"E={office_east_m:.3f} W={office_west_m:.3f} → at_office={_geq_zero(office_margin)}",
            flush=True,
        )
        print(
            f"[Compliance] country: north={north_margin:.4f} south={south_margin:.4f} "
            f"east={east_margin:.4f} west={west_margin:.4f}",
            flush=True,
        )

        final_at_home   = _geq_zero(home_margin)
        final_at_office = _geq_zero(office_margin)
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
                "company_partial_home_margin":              cp_home_north,
                "company_partial_office_margin":            cp_office_north,
                "company_partial_country_north_margin":     cp_country_north,
                "company_partial_country_south_margin":     cp_country_south,
                "company_partial_country_east_margin":      cp_country_east,
                "company_partial_country_west_margin":      cp_country_west,
            },
            margins={
                "home_margin":           home_margin,
                "office_margin":         office_margin,
                "country_north_margin":  north_margin,
                "country_south_margin":  south_margin,
                "country_east_margin":   east_margin,
                "country_west_margin":   west_margin,
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