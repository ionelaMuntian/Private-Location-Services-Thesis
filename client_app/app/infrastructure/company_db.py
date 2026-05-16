# client_app/app/infrastructure/company_db.py
from contextlib import contextmanager
from typing import Generator

import psycopg

from ..core.config import settings


@contextmanager
def get_company_connection() -> Generator[psycopg.Connection, None, None]:
    conn = psycopg.connect(settings.company_dsn)
    try:
        yield conn
    finally:
        conn.close()
