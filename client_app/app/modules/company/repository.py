from psycopg.rows import dict_row

from ...core.config import settings
from ...infrastructure.auth_db import get_auth_connection
from ...infrastructure.users_db import get_users_connection
from ...infrastructure.company_db import get_company_connection

_COMPANY_SCHEMA = "company"
_USER_SCHEMA = "user_data"

class CompanyRepository:
    def __init__(self) -> None:
        self.auth_schema = settings.auth_db_schema

    def initialize(self) -> None:
        self._init_company_db()
        self._init_users_db()

    # ------------------------------------------------------------------
    # Schema / table creation
    # ------------------------------------------------------------------

    def _init_company_db(self) -> None:
        create_schema = f"CREATE SCHEMA IF NOT EXISTS {_COMPANY_SCHEMA};"

        create_companies = f"""
        CREATE TABLE IF NOT EXISTS {_COMPANY_SCHEMA}.companies (
            id BIGSERIAL PRIMARY KEY,
            name VARCHAR(100) NOT NULL,
            allowed_country VARCHAR(100) NOT NULL,

            office_name TEXT NOT NULL,
            office_lat_m DOUBLE PRECISION NOT NULL,
            office_lon_m DOUBLE PRECISION NOT NULL,
            office_radius_m DOUBLE PRECISION NOT NULL DEFAULT 300.0,

            country_north_m DOUBLE PRECISION,
            country_south_m DOUBLE PRECISION,
            country_east_m DOUBLE PRECISION,
            country_west_m DOUBLE PRECISION,

            encrypted_office_lat_m TEXT,
            encrypted_office_lon_m TEXT,
            encrypted_office_radius_m TEXT,

            encrypted_country_policy TEXT,
            encrypted_country_north_m TEXT,
            encrypted_country_south_m TEXT,
            encrypted_country_east_m TEXT,
            encrypted_country_west_m TEXT,

            admin_user_id BIGINT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """

        create_company_users = f"""
        CREATE TABLE IF NOT EXISTS {_COMPANY_SCHEMA}.company_users (
            company_id BIGINT NOT NULL REFERENCES {_COMPANY_SCHEMA}.companies(id) ON DELETE CASCADE,
            user_id BIGINT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (company_id, user_id)
        );
        """

        create_compliance_jobs = f"""
        CREATE TABLE IF NOT EXISTS {_COMPANY_SCHEMA}.compliance_jobs (
            id BIGSERIAL PRIMARY KEY,
            company_id BIGINT NOT NULL REFERENCES {_COMPANY_SCHEMA}.companies(id) ON DELETE CASCADE,
            user_id BIGINT NOT NULL,

            encrypted_current_lat TEXT NOT NULL,
            encrypted_current_lon TEXT NOT NULL,

            encrypted_home_lat TEXT NOT NULL,
            encrypted_home_lon TEXT NOT NULL,
            encrypted_home_radius TEXT NOT NULL,

            encrypted_office_lat_m TEXT,
            encrypted_office_lon_m TEXT,
            encrypted_office_radius_m TEXT,
            encrypted_country_policy TEXT,

            encrypted_home_margin TEXT,
            encrypted_office_margin TEXT,
            encrypted_country_north_margin TEXT,
            encrypted_country_south_margin TEXT,
            encrypted_country_east_margin TEXT,
            encrypted_country_west_margin TEXT,

            user_partial_home_margin TEXT,
            user_partial_office_margin TEXT,
            user_partial_country_north_margin TEXT,
            user_partial_country_south_margin TEXT,
            user_partial_country_east_margin TEXT,
            user_partial_country_west_margin TEXT,

            company_partial_home_margin TEXT,
            company_partial_office_margin TEXT,
            company_partial_country_north_margin TEXT,
            company_partial_country_south_margin TEXT,
            company_partial_country_east_margin TEXT,
            company_partial_country_west_margin TEXT,

            decrypted_home_margin DOUBLE PRECISION,
            decrypted_office_margin DOUBLE PRECISION,
            decrypted_country_north_margin DOUBLE PRECISION,
            decrypted_country_south_margin DOUBLE PRECISION,
            decrypted_country_east_margin DOUBLE PRECISION,
            decrypted_country_west_margin DOUBLE PRECISION,

            final_at_home BOOLEAN,
            final_at_office BOOLEAN,
            final_in_country BOOLEAN,

            plaintext_at_home BOOLEAN,
            plaintext_at_office BOOLEAN,
            plaintext_in_country BOOLEAN,

            status VARCHAR(50) NOT NULL DEFAULT 'created',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """

        with get_company_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(create_schema)
                cur.execute(create_companies)
                cur.execute(create_company_users)
                cur.execute(create_compliance_jobs)
            conn.commit()

    def _init_users_db(self) -> None:
        create_schema = f"CREATE SCHEMA IF NOT EXISTS {_USER_SCHEMA};"

        create_home_locations = f"""
        CREATE TABLE IF NOT EXISTS {_USER_SCHEMA}.user_home_locations (
            user_id BIGINT PRIMARY KEY,
            encrypted_home_lat_m TEXT NOT NULL,
            encrypted_home_lon_m TEXT NOT NULL,
            home_radius_m DOUBLE PRECISION NOT NULL DEFAULT 500.0,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """

        create_location_inputs = f"""
        CREATE TABLE IF NOT EXISTS {_USER_SCHEMA}.user_location_inputs (
            company_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            current_lat_m DOUBLE PRECISION NOT NULL,
            current_lon_m DOUBLE PRECISION NOT NULL,
            home_lat_m DOUBLE PRECISION NOT NULL,
            home_lon_m DOUBLE PRECISION NOT NULL,
            home_radius_m DOUBLE PRECISION NOT NULL DEFAULT 500.0,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (company_id, user_id)
        );
        """

        create_location_status = f"""
        CREATE TABLE IF NOT EXISTS {_USER_SCHEMA}.location_status (
            company_id BIGINT NOT NULL,
            user_id BIGINT NOT NULL,
            in_country BOOLEAN,
            at_home BOOLEAN,
            at_office BOOLEAN,
            plaintext_in_country BOOLEAN,
            plaintext_at_home BOOLEAN,
            plaintext_at_office BOOLEAN,
            last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (company_id, user_id)
        );
        """

        with get_users_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(create_schema)
                cur.execute(create_home_locations)
                cur.execute(create_location_inputs)
                cur.execute(create_location_status)
            conn.commit()

    # ------------------------------------------------------------------
    # Company CRUD (company_data DB)
    # ------------------------------------------------------------------

    def create_company(self, data: dict, admin_user_id: int) -> dict:
        sql = f"""
        INSERT INTO {_COMPANY_SCHEMA}.companies (
            name, allowed_country, office_name,
            office_lat_m, office_lon_m, office_radius_m,
            country_north_m, country_south_m, country_east_m, country_west_m,
            encrypted_office_lat_m, encrypted_office_lon_m, encrypted_office_radius_m,
            encrypted_country_policy,
            encrypted_country_north_m, encrypted_country_south_m,
            encrypted_country_east_m, encrypted_country_west_m,
            admin_user_id
        )
        VALUES (
            %(name)s, %(allowed_country)s, %(office_name)s,
            %(office_lat_m)s, %(office_lon_m)s, %(office_radius_m)s,
            %(country_north_m)s, %(country_south_m)s, %(country_east_m)s, %(country_west_m)s,
            %(encrypted_office_lat_m)s, %(encrypted_office_lon_m)s, %(encrypted_office_radius_m)s,
            %(encrypted_country_policy)s,
            %(encrypted_country_north_m)s, %(encrypted_country_south_m)s,
            %(encrypted_country_east_m)s, %(encrypted_country_west_m)s,
            %(admin_user_id)s
        )
        RETURNING
            id, name, allowed_country, office_name,
            office_lat_m, office_lon_m, office_radius_m,
            country_north_m, country_south_m, country_east_m, country_west_m;
        """

        params = {
            **data,
            "encrypted_country_policy": data.get("encrypted_country_policy"),
            "encrypted_country_north_m": data.get("encrypted_country_north_m"),
            "encrypted_country_south_m": data.get("encrypted_country_south_m"),
            "encrypted_country_east_m": data.get("encrypted_country_east_m"),
            "encrypted_country_west_m": data.get("encrypted_country_west_m"),
            "admin_user_id": admin_user_id,
        }

        with get_company_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
            conn.commit()

        return dict(row)

    def update_company(self, company_id: int, data: dict, admin_user_id: int) -> dict | None:
        sql = f"""
        UPDATE {_COMPANY_SCHEMA}.companies
        SET
            name = %(name)s,
            allowed_country = %(allowed_country)s,
            office_name = %(office_name)s,
            office_lat_m = %(office_lat_m)s,
            office_lon_m = %(office_lon_m)s,
            office_radius_m = %(office_radius_m)s,
            country_north_m = %(country_north_m)s,
            country_south_m = %(country_south_m)s,
            country_east_m = %(country_east_m)s,
            country_west_m = %(country_west_m)s,
            encrypted_office_lat_m = %(encrypted_office_lat_m)s,
            encrypted_office_lon_m = %(encrypted_office_lon_m)s,
            encrypted_office_radius_m = %(encrypted_office_radius_m)s,
            encrypted_country_policy = %(encrypted_country_policy)s,
            encrypted_country_north_m = %(encrypted_country_north_m)s,
            encrypted_country_south_m = %(encrypted_country_south_m)s,
            encrypted_country_east_m = %(encrypted_country_east_m)s,
            encrypted_country_west_m = %(encrypted_country_west_m)s
        WHERE id = %(company_id)s AND admin_user_id = %(admin_user_id)s
        RETURNING
            id, name, allowed_country, office_name,
            office_lat_m, office_lon_m, office_radius_m,
            country_north_m, country_south_m, country_east_m, country_west_m;
        """

        params = {
            **data,
            "company_id": company_id,
            "admin_user_id": admin_user_id,
            "encrypted_country_policy": data.get("encrypted_country_policy"),
            "encrypted_country_north_m": data.get("encrypted_country_north_m"),
            "encrypted_country_south_m": data.get("encrypted_country_south_m"),
            "encrypted_country_east_m": data.get("encrypted_country_east_m"),
            "encrypted_country_west_m": data.get("encrypted_country_west_m"),
        }

        with get_company_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
            conn.commit()

        return dict(row) if row else None


    def delete_company(self, company_id: int, admin_user_id: int) -> bool:
        sql = f"""
        DELETE FROM {_COMPANY_SCHEMA}.companies
        WHERE id = %(company_id)s AND admin_user_id = %(admin_user_id)s
        RETURNING id;
        """

        with get_company_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"company_id": company_id, "admin_user_id": admin_user_id})
                row = cur.fetchone()
            conn.commit()

        return row is not None

    def get_company(self, company_id: int) -> dict | None:
        sql = f"""
        SELECT
            id, name, allowed_country, office_name,
            office_lat_m, office_lon_m, office_radius_m,
            country_north_m, country_south_m, country_east_m, country_west_m,
            encrypted_office_lat_m, encrypted_office_lon_m, encrypted_office_radius_m,
            encrypted_country_policy,
            encrypted_country_north_m, encrypted_country_south_m,
            encrypted_country_east_m, encrypted_country_west_m,
            admin_user_id
        FROM {_COMPANY_SCHEMA}.companies
        WHERE id = %(company_id)s
        LIMIT 1;
        """

        with get_company_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, {"company_id": company_id})
                row = cur.fetchone()

        return dict(row) if row else None

    def get_admin_companies(self, admin_user_id: int) -> list[dict]:
        sql = f"""
        SELECT
            id, name, allowed_country, office_name,
            office_lat_m, office_lon_m, office_radius_m,
            country_north_m, country_south_m, country_east_m, country_west_m
        FROM {_COMPANY_SCHEMA}.companies
        WHERE admin_user_id = %(admin_user_id)s
        ORDER BY name;
        """

        with get_company_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, {"admin_user_id": admin_user_id})
                rows = cur.fetchall()

        return [dict(row) for row in rows]

    def is_company_admin(self, company_id: int, user_id: int) -> bool:
        sql = f"""
        SELECT 1 FROM {_COMPANY_SCHEMA}.companies
        WHERE id = %(company_id)s AND admin_user_id = %(user_id)s
        LIMIT 1;
        """

        with get_company_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"company_id": company_id, "user_id": user_id})
                row = cur.fetchone()

        return row is not None

    # ------------------------------------------------------------------
    # Company membership (company_data DB)
    # ------------------------------------------------------------------

    def add_employee_to_company(self, company_id: int, user_id: int) -> None:
        sql = f"""
        INSERT INTO {_COMPANY_SCHEMA}.company_users (company_id, user_id)
        VALUES (%(company_id)s, %(user_id)s)
        ON CONFLICT (company_id, user_id) DO NOTHING;
        """

        with get_company_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"company_id": company_id, "user_id": user_id})
            conn.commit()

    def join_company(self, company_id: int, user_id: int) -> None:
        self.add_employee_to_company(company_id=company_id, user_id=user_id)

    def is_employee_of_company(self, company_id: int, user_id: int) -> bool:
        sql = f"""
        SELECT 1 FROM {_COMPANY_SCHEMA}.company_users
        WHERE company_id = %(company_id)s AND user_id = %(user_id)s
        LIMIT 1;
        """


        with get_company_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"company_id": company_id, "user_id": user_id})
                row = cur.fetchone()

        return row is not None

    def get_user_companies(self, user_id: int) -> list[dict]:
        sql = f"""
        SELECT
            c.id, c.name, c.allowed_country, c.office_name,
            c.office_lat_m, c.office_lon_m, c.office_radius_m,
            c.country_north_m, c.country_south_m, c.country_east_m, c.country_west_m
        FROM {_COMPANY_SCHEMA}.companies c
        JOIN {_COMPANY_SCHEMA}.company_users cu ON cu.company_id = c.id
        WHERE cu.user_id = %(user_id)s
        ORDER BY c.name;
        """

        with get_company_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, {"user_id": user_id})
                rows = cur.fetchall()

        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # User lookups (auth_data DB — read-only cross-reference)
    # ------------------------------------------------------------------

    def get_user_summary(self, user_id: int) -> dict | None:
        sql = f"""
        SELECT id, username, email
        FROM {self.auth_schema}.users
        WHERE id = %(user_id)s
        LIMIT 1;
        """

        with get_auth_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, {"user_id": user_id})
                row = cur.fetchone()

        return dict(row) if row else None

    def _get_users_by_ids(self, user_ids: list[int]) -> dict[int, dict]:
        if not user_ids:
            return {}

        sql = f"""
        SELECT id, username, email
        FROM {self.auth_schema}.users
        WHERE id = ANY(%(user_ids)s);
        """

        with get_auth_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, {"user_ids": user_ids})
                rows = cur.fetchall()

        return {row["id"]: dict(row) for row in rows}

    # ------------------------------------------------------------------
    # User data (users_data DB)
    # ------------------------------------------------------------------

    def save_latest_location_input(self, user_id: int, data: dict) -> None:
        sql = f"""
        INSERT INTO {_USER_SCHEMA}.user_location_inputs (
            company_id, user_id,
            current_lat_m, current_lon_m,
            home_lat_m, home_lon_m, home_radius_m,
            updated_at
        )
        VALUES (
            %(company_id)s, %(user_id)s,
            %(current_lat_m)s, %(current_lon_m)s,
            %(home_lat_m)s, %(home_lon_m)s, %(home_radius_m)s,
            NOW()
        )
        ON CONFLICT (company_id, user_id)
        DO UPDATE SET
            current_lat_m = EXCLUDED.current_lat_m,
            current_lon_m = EXCLUDED.current_lon_m,
            home_lat_m = EXCLUDED.home_lat_m,
            home_lon_m = EXCLUDED.home_lon_m,
            home_radius_m = EXCLUDED.home_radius_m,
            updated_at = NOW();
        """

        with get_users_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {
                    "company_id": data["company_id"],
                    "user_id": user_id,
                    "current_lat_m": data["current_lat_m"],
                    "current_lon_m": data["current_lon_m"],
                    "home_lat_m": data["home_lat_m"],
                    "home_lon_m": data["home_lon_m"],
                    "home_radius_m": data["home_radius_m"],
                })
            conn.commit()

    def get_latest_location_input(self, company_id: int, user_id: int) -> dict | None:
        sql = f"""
        SELECT
            company_id, user_id,
            current_lat_m, current_lon_m,
            home_lat_m, home_lon_m, home_radius_m,
            updated_at::text AS updated_at
        FROM {_USER_SCHEMA}.user_location_inputs
        WHERE company_id = %(company_id)s AND user_id = %(user_id)s
        LIMIT 1;
        """

        with get_users_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, {"company_id": company_id, "user_id": user_id})
                row = cur.fetchone()

        return dict(row) if row else None

    def save_encrypted_home(self, user_id: int, data: dict) -> None:
        sql = f"""
        INSERT INTO {_USER_SCHEMA}.user_home_locations (
            user_id, encrypted_home_lat_m, encrypted_home_lon_m, home_radius_m, updated_at
        )
        VALUES (%(user_id)s, %(encrypted_home_lat_m)s, %(encrypted_home_lon_m)s, %(home_radius_m)s, NOW())
        ON CONFLICT (user_id)
        DO UPDATE SET
            encrypted_home_lat_m = EXCLUDED.encrypted_home_lat_m,
            encrypted_home_lon_m = EXCLUDED.encrypted_home_lon_m,
            home_radius_m = EXCLUDED.home_radius_m,
            updated_at = NOW();
        """

        with get_users_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {
                    "user_id": user_id,
                    "encrypted_home_lat_m": data["encrypted_home_lat_m"],
                    "encrypted_home_lon_m": data["encrypted_home_lon_m"],
                    "home_radius_m": data["home_radius_m"],
                })
            conn.commit()

    def clear_location_status(self, user_id: int, company_id: int) -> None:
        sql = f"""
        DELETE FROM {_USER_SCHEMA}.location_status
        WHERE user_id = %(user_id)s AND company_id = %(company_id)s;
        """

        with get_users_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {"user_id": user_id, "company_id": company_id})
            conn.commit()

    def submit_status(self, user_id: int, data: dict) -> None:
        sql = f"""
        INSERT INTO {_USER_SCHEMA}.location_status (
            company_id, user_id,
            in_country, at_home, at_office,
            plaintext_in_country, plaintext_at_home, plaintext_at_office,
            last_updated
        )
        VALUES (
            %(company_id)s, %(user_id)s,
            %(in_country)s, %(at_home)s, %(at_office)s,
            %(plaintext_in_country)s, %(plaintext_at_home)s, %(plaintext_at_office)s,
            NOW()
        )
        ON CONFLICT (company_id, user_id)
        DO UPDATE SET
            in_country = EXCLUDED.in_country,
            at_home = EXCLUDED.at_home,
            at_office = EXCLUDED.at_office,
            plaintext_in_country = EXCLUDED.plaintext_in_country,
            plaintext_at_home = EXCLUDED.plaintext_at_home,
            plaintext_at_office = EXCLUDED.plaintext_at_office,
            last_updated = NOW();
        """

        with get_users_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, {
                    "company_id": data["company_id"],
                    "user_id": user_id,
                    "in_country": data["in_country"],
                    "at_home": data["at_home"],
                    "at_office": data["at_office"],
                    "plaintext_in_country": data.get("plaintext_in_country"),
                    "plaintext_at_home": data.get("plaintext_at_home"),
                    "plaintext_at_office": data.get("plaintext_at_office"),
                })
            conn.commit()

    def get_user_location_status(self, user_id: int, company_id: int) -> dict | None:
        sql = f"""
        SELECT
            company_id, user_id,
            in_country, at_home, at_office,
            last_updated::text AS last_updated
        FROM {_USER_SCHEMA}.location_status
        WHERE user_id = %(user_id)s AND company_id = %(company_id)s
        LIMIT 1;
        """

        with get_users_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, {"user_id": user_id, "company_id": company_id})
                row = cur.fetchone()

        return dict(row) if row else None

    def get_users_status(self, company_id: int) -> list[dict]:
        # Step 1: employee user_ids from company_data
        with get_company_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"SELECT user_id FROM {_COMPANY_SCHEMA}.company_users WHERE company_id = %s",
                    (company_id,),
                )
                user_ids = [row["user_id"] for row in cur.fetchall()]

        if not user_ids:
            return []

        # Step 2: user info from auth_data
        users_by_id = self._get_users_by_ids(user_ids)

        # Step 3: location statuses from users_data
        with get_users_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    f"""
                    SELECT
                        user_id, in_country, at_home, at_office,
                        plaintext_in_country, plaintext_at_home, plaintext_at_office,
                        last_updated::text AS last_updated
                    FROM {_USER_SCHEMA}.location_status
                    WHERE company_id = %s AND user_id = ANY(%s)
                    """,
                    (company_id, user_ids),
                )
                statuses_by_id = {row["user_id"]: dict(row) for row in cur.fetchall()}

        # Step 4: combine and return sorted by username
        result = []
        for uid in user_ids:
            user = users_by_id.get(uid, {})
            status = statuses_by_id.get(uid, {})
            result.append({
                "user_id": uid,
                "username": user.get("username"),
                "email": user.get("email"),
                "in_country": status.get("in_country"),
                "at_home": status.get("at_home"),
                "at_office": status.get("at_office"),
                "plaintext_in_country": status.get("plaintext_in_country"),
                "plaintext_at_home": status.get("plaintext_at_home"),
                "plaintext_at_office": status.get("plaintext_at_office"),
                "last_updated": status.get("last_updated"),
            })

        return sorted(result, key=lambda x: x.get("username") or "")

    # ------------------------------------------------------------------
    # Compliance jobs (company_data DB)
    # ------------------------------------------------------------------

    def create_compliance_job(self, user_id: int, data: dict, company: dict) -> dict:
        sql = f"""
        INSERT INTO {_COMPANY_SCHEMA}.compliance_jobs (
            company_id, user_id,
            encrypted_current_lat, encrypted_current_lon,
            encrypted_home_lat, encrypted_home_lon, encrypted_home_radius,
            encrypted_office_lat_m, encrypted_office_lon_m, encrypted_office_radius_m,
            encrypted_country_policy,
            encrypted_home_margin, encrypted_office_margin,
            encrypted_country_north_margin, encrypted_country_south_margin,
            encrypted_country_east_margin, encrypted_country_west_margin,
            status
        )
        VALUES (
            %(company_id)s, %(user_id)s,
            %(encrypted_current_lat)s, %(encrypted_current_lon)s,
            %(encrypted_home_lat)s, %(encrypted_home_lon)s, %(encrypted_home_radius)s,
            %(encrypted_office_lat_m)s, %(encrypted_office_lon_m)s, %(encrypted_office_radius_m)s,
            %(encrypted_country_policy)s,
            %(encrypted_home_margin)s, %(encrypted_office_margin)s,
            %(encrypted_country_north_margin)s, %(encrypted_country_south_margin)s,
            %(encrypted_country_east_margin)s, %(encrypted_country_west_margin)s,
            'encrypted_margins_ready'
        )
        RETURNING id, status;
        """

        params = {
            "company_id": data["company_id"],
            "user_id": user_id,
            "encrypted_current_lat": data["encrypted_current_lat"],
            "encrypted_current_lon": data["encrypted_current_lon"],
            "encrypted_home_lat": data["encrypted_home_lat"],
            "encrypted_home_lon": data["encrypted_home_lon"],
            "encrypted_home_radius": data["encrypted_home_radius"],
            "encrypted_office_lat_m": company.get("encrypted_office_lat_m"),
            "encrypted_office_lon_m": company.get("encrypted_office_lon_m"),
            "encrypted_office_radius_m": company.get("encrypted_office_radius_m"),
            "encrypted_country_policy": company.get("encrypted_country_policy"),
            "encrypted_home_margin": data["encrypted_home_margin"],
            "encrypted_office_margin": data["encrypted_office_margin"],
            "encrypted_country_north_margin": data["encrypted_country_north_margin"],
            "encrypted_country_south_margin": data["encrypted_country_south_margin"],
            "encrypted_country_east_margin": data["encrypted_country_east_margin"],
            "encrypted_country_west_margin": data["encrypted_country_west_margin"],
        }

        with get_company_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
            conn.commit()

        return dict(row)

    def get_compliance_job(self, job_id: int) -> dict | None:
        sql = f"""
        SELECT
            id, company_id, user_id, status,
            encrypted_current_lat, encrypted_current_lon,
            encrypted_home_lat, encrypted_home_lon, encrypted_home_radius,
            encrypted_home_margin, encrypted_office_margin,
            encrypted_country_north_margin, encrypted_country_south_margin,
            encrypted_country_east_margin, encrypted_country_west_margin,
            user_partial_home_margin, user_partial_office_margin,
            user_partial_country_north_margin, user_partial_country_south_margin,
            user_partial_country_east_margin, user_partial_country_west_margin,
            company_partial_home_margin, company_partial_office_margin,
            company_partial_country_north_margin, company_partial_country_south_margin,
            company_partial_country_east_margin, company_partial_country_west_margin,
            decrypted_home_margin, decrypted_office_margin,
            decrypted_country_north_margin, decrypted_country_south_margin,
            decrypted_country_east_margin, decrypted_country_west_margin,
            final_at_home, final_at_office, final_in_country
        FROM {_COMPANY_SCHEMA}.compliance_jobs
        WHERE id = %(job_id)s
        LIMIT 1;
        """

        with get_company_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, {"job_id": job_id})
                row = cur.fetchone()

        return dict(row) if row else None

    def store_user_partials(self, job_id: int, user_id: int, partials: dict) -> dict | None:
        sql = f"""
        UPDATE {_COMPANY_SCHEMA}.compliance_jobs
        SET
            user_partial_home_margin = %(user_partial_home_margin)s,
            user_partial_office_margin = %(user_partial_office_margin)s,
            user_partial_country_north_margin = %(user_partial_country_north_margin)s,
            user_partial_country_south_margin = %(user_partial_country_south_margin)s,
            user_partial_country_east_margin = %(user_partial_country_east_margin)s,
            user_partial_country_west_margin = %(user_partial_country_west_margin)s,
            status = 'user_partials_submitted',
            updated_at = NOW()
        WHERE id = %(job_id)s AND user_id = %(user_id)s
        RETURNING id, status;
        """

        params = {"job_id": job_id, "user_id": user_id, **partials}

        with get_company_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
            conn.commit()

        return dict(row) if row else None

    def store_company_fusion_result(
        self,
        job_id: int,
        company_partials: dict,
        margins: dict,
        final_at_home: bool,
        final_at_office: bool,
        final_in_country: bool,
        plaintext_at_home: bool | None = None,
        plaintext_at_office: bool | None = None,
        plaintext_in_country: bool | None = None,
    ) -> dict | None:
        sql = f"""
        UPDATE {_COMPANY_SCHEMA}.compliance_jobs
        SET
            company_partial_home_margin = %(company_partial_home_margin)s,
            company_partial_office_margin = %(company_partial_office_margin)s,
            company_partial_country_north_margin = %(company_partial_country_north_margin)s,
            company_partial_country_south_margin = %(company_partial_country_south_margin)s,
            company_partial_country_east_margin = %(company_partial_country_east_margin)s,
            company_partial_country_west_margin = %(company_partial_country_west_margin)s,

            decrypted_home_margin = %(home_margin)s,
            decrypted_office_margin = %(office_margin)s,
            decrypted_country_north_margin = %(country_north_margin)s,
            decrypted_country_south_margin = %(country_south_margin)s,
            decrypted_country_east_margin = %(country_east_margin)s,
            decrypted_country_west_margin = %(country_west_margin)s,

            final_at_home = %(final_at_home)s,
            final_at_office = %(final_at_office)s,
            final_in_country = %(final_in_country)s,

            plaintext_at_home = %(plaintext_at_home)s,
            plaintext_at_office = %(plaintext_at_office)s,
            plaintext_in_country = %(plaintext_in_country)s,

            status = 'completed',
            updated_at = NOW()
        WHERE id = %(job_id)s
        RETURNING
            id, status,
            final_at_home, final_at_office, final_in_country,
            plaintext_at_home, plaintext_at_office, plaintext_in_country;
        """

        params = {
            "job_id": job_id,
            **company_partials,
            **margins,
            "final_at_home": final_at_home,
            "final_at_office": final_at_office,
            "final_in_country": final_in_country,
            "plaintext_at_home": plaintext_at_home,
            "plaintext_at_office": plaintext_at_office,
            "plaintext_in_country": plaintext_in_country,
        }

        with get_company_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
            conn.commit()

        return dict(row) if row else None

    def mark_compliance_job_completed(
        self,
        job_id: int,
        final_at_home: bool,
        final_at_office: bool,
        final_in_country: bool,
    ) -> dict | None:
        sql = f"""
        UPDATE {_COMPANY_SCHEMA}.compliance_jobs
        SET
            final_at_home = %(final_at_home)s,
            final_at_office = %(final_at_office)s,
            final_in_country = %(final_in_country)s,
            status = 'completed',
            updated_at = NOW()
        WHERE id = %(job_id)s
        RETURNING id, status, final_at_home, final_at_office, final_in_country;
        """

        with get_company_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, {
                    "job_id": job_id,
                    "final_at_home": final_at_home,
                    "final_at_office": final_at_office,
                    "final_in_country": final_in_country,
                })
                row = cur.fetchone()
            conn.commit()

        return dict(row) if row else None
