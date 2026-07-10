from fastapi import HTTPException, status

from ...core.openfhe_multiparty_instance import openfhe_multiparty_runtime
from ...infrastructure.grpc_client import post_to_service_provider
from .repository import CompanyRepository
from .schemas import AddEmployeeRequest, CreateCompanyRequest

repository = CompanyRepository()

# The tolerance the system has when the user sits near the boundary
EPSILON = 1e-3

COORD_SCALE = 100.0


def _less_than_equal_zero(value: float) -> bool:
    return value <= EPSILON


def _greater_than_equal_zero(value: float) -> bool:
    return value >= -EPSILON


def _compute_plaintext_compliance(location_input: dict, company: dict) -> dict:

    # user coordinates
    current_lat = float(location_input["current_lat_m"])
    current_lon = float(location_input["current_lon_m"])

    # home coordinates
    home_lat = float(location_input["home_lat_m"])
    home_lon = float(location_input["home_lon_m"])
    home_radius = float(location_input["home_radius_m"])

    # office coordinates
    office_lat = float(company["office_lat_m"])
    office_lon = float(company["office_lon_m"])
    office_radius = float(company["office_radius_m"])

    # home check
    plaintext_at_home = (
        home_lat - home_radius <= current_lat <= home_lat + home_radius
        and home_lon - home_radius <= current_lon <= home_lon + home_radius
    )

    # office check
    plaintext_at_office = (
        office_lat - office_radius <= current_lat <= office_lat + office_radius
        and office_lon - office_radius <= current_lon <= office_lon + office_radius
    )

    # country coordinates
    north = company.get("country_north_m")
    south = company.get("country_south_m")
    east = company.get("country_east_m")
    west = company.get("country_west_m")

    # country check
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


class CompanyAdminService:
    def initialize_storage(self) -> None:
        repository.initialize()

    # store the country coordinates in encrypted form
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
                detail="Only company administrators can update this company",
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
            raise HTTPException(status_code=404, detail="Company not found")

        return result

    def delete_company(self, company_id: int, current_user: dict) -> dict:
        if not repository.is_company_admin(company_id, current_user["id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only company administrators can delete this company",
            )

        deleted = repository.delete_company(company_id, current_user["id"])
        if not deleted:
            raise HTTPException(status_code=404, detail="Company not found")

        return {"message": "Company deleted successfully.", "company_id": company_id}

    def get_my_admin_companies(self, current_user: dict) -> dict:
        companies = repository.get_admin_companies(current_user["id"])
        return {"companies": companies}

    def add_employee(self, request: AddEmployeeRequest, current_user: dict) -> dict:
        company = repository.get_company(request.company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")

        if not repository.is_company_admin(request.company_id, current_user["id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only company administrators can add employees",
            )

        repository.add_employee_to_company(
            company_id=request.company_id,
            user_id=request.user_id,
        )

        return {
            "message": "Employee added successfully",
            "company_id": request.company_id,
            "user_id": request.user_id,
        }

    def get_users_status(self, company_id: int, current_user: dict) -> dict:
        company = repository.get_company(company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Company not found")

        if not repository.is_company_admin(company_id, current_user["id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only company administrators can view employee statuses",
            )

        users = repository.get_users_status(company_id)

        return {
            "company_id": company["id"],
            "company_name": company["name"],
            "users": users,
        }

    async def run_employee_compliance_check(self, company_id: int, employee_user_id: int, current_user: dict,) -> dict:
        company = repository.get_company(company_id)
        if company is None:
            raise HTTPException(status_code=404, detail="Company is not found")

        if not repository.is_company_admin(company_id, current_user["id"]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only the company administrators can run compliance checks",
            )

        if not repository.is_employee_of_company(company_id, employee_user_id):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Selected user is not assigned to this company",
            )

        location_input = repository.get_latest_location_input(
            company_id=company_id,
            user_id=employee_user_id,
        )

        if location_input is None:
            raise HTTPException(
                status_code=422,
                detail=(
                    "No prepared location data exists for this employee"
                    "The employee must first press Share / Update Location"
                ),
            )

        enc = openfhe_multiparty_runtime.encrypt_scalar

        # encrypt the user coordinate after scaling them
        encrypted_current_lat = enc(location_input["current_lat_m"] / COORD_SCALE)
        encrypted_current_lon = enc(location_input["current_lon_m"] / COORD_SCALE)

        # scale the home coordinates
        home_lat_sc = location_input["home_lat_m"] / COORD_SCALE
        home_lon_sc = location_input["home_lon_m"] / COORD_SCALE
        home_r_sc = location_input["home_radius_m"] / COORD_SCALE

        # encrypt and compute the bounding box margins of home
        encrypted_home_north = enc(home_lat_sc + home_r_sc)
        encrypted_home_south = enc(home_lat_sc - home_r_sc)
        encrypted_home_east = enc(home_lon_sc + home_r_sc)
        encrypted_home_west = enc(home_lon_sc - home_r_sc)

        # encrypt the home coordinates
        encrypted_home_lat = enc(home_lat_sc)
        encrypted_home_lon = enc(home_lon_sc)
        encrypted_home_radius = enc(home_r_sc)

        # scale the company coordinates
        office_lat_sc = company["office_lat_m"] / COORD_SCALE
        office_lon_sc = company["office_lon_m"] / COORD_SCALE
        office_r_sc = company["office_radius_m"] / COORD_SCALE

        # encrypt and compute the bounding box margins of office
        encrypted_office_north = enc(office_lat_sc + office_r_sc)
        encrypted_office_south = enc(office_lat_sc - office_r_sc)
        encrypted_office_east = enc(office_lon_sc + office_r_sc)
        encrypted_office_west = enc(office_lon_sc - office_r_sc)

        # encrypt and scale the coordinates of country
        encrypted_country_north = enc((company["country_north_m"] or 0.0) / COORD_SCALE)
        encrypted_country_south = enc((company["country_south_m"] or 0.0) / COORD_SCALE)
        encrypted_country_east = enc((company["country_east_m"] or 0.0) / COORD_SCALE)
        encrypted_country_west = enc((company["country_west_m"] or 0.0) / COORD_SCALE)

        service_payload = {
            "metadata": {
                "crypto_context": openfhe_multiparty_runtime.serialize_crypto_context(),
                "eval_mult_keys": openfhe_multiparty_runtime.serialize_eval_mult_keys(),
            },
            "encrypted_current_lat": encrypted_current_lat,
            "encrypted_current_lon": encrypted_current_lon,
            "encrypted_home_north": encrypted_home_north,
            "encrypted_home_south": encrypted_home_south,
            "encrypted_home_east": encrypted_home_east,
            "encrypted_home_west": encrypted_home_west,
            "encrypted_office_north": encrypted_office_north,
            "encrypted_office_south": encrypted_office_south,
            "encrypted_office_east": encrypted_office_east,
            "encrypted_office_west": encrypted_office_west,
            "encrypted_country_north": encrypted_country_north,
            "encrypted_country_south": encrypted_country_south,
            "encrypted_country_east": encrypted_country_east,
            "encrypted_country_west": encrypted_country_west,
        }

        # send the coordinates to the server to run the compliance check
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
                "encrypted_home_margin": encrypted_margins["encrypted_home_north_margin"],
                "encrypted_office_margin": encrypted_margins["encrypted_office_north_margin"],
                "encrypted_country_north_margin": encrypted_margins["encrypted_country_north_margin"],
                "encrypted_country_south_margin": encrypted_margins["encrypted_country_south_margin"],
                "encrypted_country_east_margin": encrypted_margins["encrypted_country_east_margin"],
                "encrypted_country_west_margin": encrypted_margins["encrypted_country_west_margin"],
            },
            company=company,
        )

        job_id = int(job["id"])

        openfhe_multiparty_runtime.refresh_context()

        # decryptors
        first = openfhe_multiparty_runtime.user_partial_decrypt_scalar
        second = openfhe_multiparty_runtime.company_partial_decrypt_scalar
        fuse = openfhe_multiparty_runtime.company_fuse_scalar

        # Client decrypts the home margins and obtains partially decrypted results
        first_home_north = first(encrypted_margins["encrypted_home_north_margin"])
        first_home_south = first(encrypted_margins["encrypted_home_south_margin"])
        first_home_east = first(encrypted_margins["encrypted_home_east_margin"])
        first_home_west = first(encrypted_margins["encrypted_home_west_margin"])

        # Client decrypts the office margins and obtains partially decrypted results
        first_office_north = first(encrypted_margins["encrypted_office_north_margin"])
        first_office_south = first(encrypted_margins["encrypted_office_south_margin"])
        first_office_east = first(encrypted_margins["encrypted_office_east_margin"])
        first_office_west = first(encrypted_margins["encrypted_office_west_margin"])

        # Client decrypts the country margins and obtains partially decrypted results
        first_country_north = first(encrypted_margins["encrypted_country_north_margin"])
        first_country_south = first(encrypted_margins["encrypted_country_south_margin"])
        first_country_east = first(encrypted_margins["encrypted_country_east_margin"])
        first_country_west = first(encrypted_margins["encrypted_country_west_margin"])

        repository.store_user_partials(
            job_id=job_id,
            user_id=employee_user_id,
            partials={
                "user_partial_home_margin":              first_home_north,
                "user_partial_office_margin":            first_office_north,
                "user_partial_country_north_margin":     first_country_north,
                "user_partial_country_south_margin":     first_country_south,
                "user_partial_country_east_margin":      first_country_east,
                "user_partial_country_west_margin":      first_country_west,
            },
        )

        # Company decrypts the home margins and obtains partially decrypted results
        second_home_north = second(encrypted_margins["encrypted_home_north_margin"])
        second_home_south = second(encrypted_margins["encrypted_home_south_margin"])
        second_home_east = second(encrypted_margins["encrypted_home_east_margin"])
        second_home_west = second(encrypted_margins["encrypted_home_west_margin"])

        # Company decrypts the office margins and obtains partially decrypted results
        second_office_north = second(encrypted_margins["encrypted_office_north_margin"])
        second_office_south = second(encrypted_margins["encrypted_office_south_margin"])
        second_office_east = second(encrypted_margins["encrypted_office_east_margin"])
        second_office_west = second(encrypted_margins["encrypted_office_west_margin"])

        # Company decrypts the country margins and obtains partially decrypted results
        second_country_north = second(encrypted_margins["encrypted_country_north_margin"])
        second_country_south = second(encrypted_margins["encrypted_country_south_margin"])
        second_country_east = second(encrypted_margins["encrypted_country_east_margin"])
        second_country_west = second(encrypted_margins["encrypted_country_west_margin"])

        # The fusion of the partially decrypted results for home
        home_north_m = fuse(first_home_north, second_home_north)
        home_south_m = fuse(first_home_south, second_home_south)
        home_east_m = fuse(first_home_east, second_home_east)
        home_west_m = fuse(first_home_west, second_home_west)

        # The fusion of the partially decrypted results for office
        office_north_m = fuse(first_office_north, second_office_north)
        office_south_m = fuse(first_office_south, second_office_south)
        office_east_m = fuse(first_office_east,  second_office_east)
        office_west_m = fuse(first_office_west,  second_office_west)

        # The fusion of the partially decrypted results for country
        north_margin = fuse(first_country_north, second_country_north)
        south_margin = fuse(first_country_south, second_country_south)
        east_margin = fuse(first_country_east,  second_country_east)
        west_margin = fuse(first_country_west,  second_country_west)

        # Find the smallest margin
        # If the smallest margin is greater than zero, it means that all margins are
        home_margin = min(home_north_m, home_south_m, home_east_m, home_west_m)
        office_margin = min(office_north_m, office_south_m, office_east_m, office_west_m)

        # final decisions on whether the user is at home, office or country
        final_at_home = _greater_than_equal_zero(home_margin)
        final_at_office = _greater_than_equal_zero(office_margin)
        final_in_country = (
            _greater_than_equal_zero(north_margin)
            and _greater_than_equal_zero(south_margin)
            and _greater_than_equal_zero(east_margin)
            and _greater_than_equal_zero(west_margin)
        )

        plaintext = _compute_plaintext_compliance(location_input, company)

        result = repository.store_company_fusion_result(
            job_id=job_id,
            company_partials={
                "company_partial_home_margin":              second_home_north,
                "company_partial_office_margin":            second_office_north,
                "company_partial_country_north_margin":     second_country_north,
                "company_partial_country_south_margin":     second_country_south,
                "company_partial_country_east_margin":      second_country_east,
                "company_partial_country_west_margin":      second_country_west,
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
