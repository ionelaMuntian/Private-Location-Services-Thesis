from psycopg.rows import dict_row

from ...infrastructure.auth_db import get_auth_connection


class CompanyRepository:
    def initialize(self) -> None:
        sql = """
        CREATE SCHEMA IF NOT EXISTS company;

        CREATE TABLE IF NOT EXISTS company.companies (
            id BIGSERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            allowed_country TEXT NOT NULL,
            office_name TEXT NOT NULL,
            office_lat_m DOUBLE PRECISION NOT NULL,
            office_lon_m DOUBLE PRECISION NOT NULL,
            office_radius_m DOUBLE PRECISION NOT NULL DEFAULT 300,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );

        CREATE TABLE IF NOT EXISTS company.company_admins (
            id BIGSERIAL PRIMARY KEY,
            company_id BIGINT NOT NULL REFERENCES company.companies(id) ON DELETE CASCADE,
            user_id BIGINT NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(company_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS company.company_users (
            id BIGSERIAL PRIMARY KEY,
            company_id BIGINT NOT NULL REFERENCES company.companies(id) ON DELETE CASCADE,
            user_id BIGINT NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(company_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS company.user_home_locations (
            id BIGSERIAL PRIMARY KEY,
            user_id BIGINT NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            encrypted_home_lat_m TEXT NOT NULL,
            encrypted_home_lon_m TEXT NOT NULL,
            home_radius_m DOUBLE PRECISION NOT NULL DEFAULT 500,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(user_id)
        );

        CREATE TABLE IF NOT EXISTS company.user_location_status (
            id BIGSERIAL PRIMARY KEY,
            company_id BIGINT NOT NULL REFERENCES company.companies(id) ON DELETE CASCADE,
            user_id BIGINT NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
            in_country BOOLEAN,
            at_home BOOLEAN,
            at_office BOOLEAN,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE(company_id, user_id)
        );
        """

        with get_auth_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
            conn.commit()

    def create_company(self, data: dict, admin_user_id: int) -> dict:
        with get_auth_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    INSERT INTO company.companies
                    (name, allowed_country, office_name, office_lat_m, office_lon_m, office_radius_m)
                    VALUES
                    (%(name)s, %(allowed_country)s, %(office_name)s, %(office_lat_m)s, %(office_lon_m)s, %(office_radius_m)s)
                    RETURNING *;
                    """,
                    data,
                )
                company = dict(cur.fetchone())

                cur.execute(
                    """
                    INSERT INTO company.company_admins (company_id, user_id)
                    VALUES (%(company_id)s, %(user_id)s)
                    ON CONFLICT DO NOTHING;
                    """,
                    {"company_id": company["id"], "user_id": admin_user_id},
                )

                cur.execute(
                    """
                    INSERT INTO company.company_users (company_id, user_id)
                    VALUES (%(company_id)s, %(user_id)s)
                    ON CONFLICT DO NOTHING;
                    """,
                    {"company_id": company["id"], "user_id": admin_user_id},
                )

            conn.commit()

        return company

    def join_company(self, company_id: int, user_id: int) -> None:
        with get_auth_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO company.company_users (company_id, user_id)
                    VALUES (%(company_id)s, %(user_id)s)
                    ON CONFLICT DO NOTHING;
                    """,
                    {"company_id": company_id, "user_id": user_id},
                )
            conn.commit()

    def is_company_admin(self, company_id: int, user_id: int) -> bool:
        with get_auth_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT 1
                    FROM company.company_admins
                    WHERE company_id = %(company_id)s
                      AND user_id = %(user_id)s
                    LIMIT 1;
                    """,
                    {"company_id": company_id, "user_id": user_id},
                )
                return cur.fetchone() is not None

    def save_encrypted_home(self, user_id: int, data: dict) -> None:
        with get_auth_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO company.user_home_locations
                    (user_id, encrypted_home_lat_m, encrypted_home_lon_m, home_radius_m)
                    VALUES
                    (%(user_id)s, %(encrypted_home_lat_m)s, %(encrypted_home_lon_m)s, %(home_radius_m)s)
                    ON CONFLICT (user_id)
                    DO UPDATE SET
                        encrypted_home_lat_m = EXCLUDED.encrypted_home_lat_m,
                        encrypted_home_lon_m = EXCLUDED.encrypted_home_lon_m,
                        home_radius_m = EXCLUDED.home_radius_m,
                        updated_at = NOW();
                    """,
                    {"user_id": user_id, **data},
                )
            conn.commit()

    def submit_status(self, user_id: int, data: dict) -> None:
        with get_auth_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO company.user_location_status
                    (company_id, user_id, in_country, at_home, at_office)
                    VALUES
                    (%(company_id)s, %(user_id)s, %(in_country)s, %(at_home)s, %(at_office)s)
                    ON CONFLICT (company_id, user_id)
                    DO UPDATE SET
                        in_country = EXCLUDED.in_country,
                        at_home = EXCLUDED.at_home,
                        at_office = EXCLUDED.at_office,
                        updated_at = NOW();
                    """,
                    {"user_id": user_id, **data},
                )
            conn.commit()

    def get_company(self, company_id: int) -> dict | None:
        with get_auth_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT *
                    FROM company.companies
                    WHERE id = %(company_id)s;
                    """,
                    {"company_id": company_id},
                )
                row = cur.fetchone()

        return dict(row) if row else None

    def get_users_status(self, company_id: int) -> list[dict]:
        with get_auth_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    """
                    SELECT
                        u.id AS user_id,
                        u.username,
                        u.email,
                        s.in_country,
                        s.at_home,
                        s.at_office,
                        s.updated_at::text AS last_updated
                    FROM company.company_users cu
                    JOIN auth.users u ON u.id = cu.user_id
                    LEFT JOIN company.user_location_status s
                        ON s.company_id = cu.company_id
                       AND s.user_id = cu.user_id
                    WHERE cu.company_id = %(company_id)s
                    ORDER BY u.username;
                    """,
                    {"company_id": company_id},
                )
                rows = cur.fetchall()

        return [dict(row) for row in rows]