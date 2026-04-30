# client_app/app/modules/auth/repository.py
from psycopg.rows import dict_row

from ...core.config import settings
from ...infrastructure.auth_db import get_auth_connection


class AuthRepository:
    def __init__(self) -> None:
        self.schema = settings.auth_db_schema

    def create_schema_and_table_if_not_exists(self) -> None:
        create_schema_sql = f"""
        CREATE SCHEMA IF NOT EXISTS {self.schema};
        """

        create_table_sql = f"""
        CREATE TABLE IF NOT EXISTS {self.schema}.users (
            id BIGSERIAL PRIMARY KEY,
            username VARCHAR(50) NOT NULL UNIQUE,
            email VARCHAR(255) NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        );
        """

        with get_auth_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(create_schema_sql)
                cur.execute(create_table_sql)
            conn.commit()

    def get_user_by_username(self, username: str) -> dict | None:
        sql = f"""
        SELECT id, username, email, password_hash, is_active
        FROM {self.schema}.users
        WHERE username = %(username)s
        LIMIT 1;
        """

        with get_auth_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, {"username": username})
                row = cur.fetchone()

        return dict(row) if row else None

    def get_user_by_email(self, email: str) -> dict | None:
        sql = f"""
        SELECT id, username, email, password_hash, is_active
        FROM {self.schema}.users
        WHERE email = %(email)s
        LIMIT 1;
        """

        with get_auth_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, {"email": email})
                row = cur.fetchone()

        return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> dict | None:
        sql = f"""
        SELECT id, username, email, password_hash, is_active
        FROM {self.schema}.users
        WHERE id = %(user_id)s
        LIMIT 1;
        """

        with get_auth_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(sql, {"user_id": user_id})
                row = cur.fetchone()

        return dict(row) if row else None

    def create_user(self, username: str, email: str, password_hash: str) -> dict:
        sql = f"""
        INSERT INTO {self.schema}.users (username, email, password_hash)
        VALUES (%(username)s, %(email)s, %(password_hash)s)
        RETURNING id, username, email, is_active;
        """

        with get_auth_connection() as conn:
            with conn.cursor(row_factory=dict_row) as cur:
                cur.execute(
                    sql,
                    {
                        "username": username,
                        "email": email,
                        "password_hash": password_hash,
                    },
                )
                row = cur.fetchone()
            conn.commit()

        return dict(row)