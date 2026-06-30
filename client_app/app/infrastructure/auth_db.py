from contextlib import contextmanager
from typing import Generator

import psycopg

from ..core.config import settings


@contextmanager
def get_auth_connection() -> Generator[psycopg.Connection, None, None]:
    conn = psycopg.connect(settings.auth_dsn)
    try:
        yield conn
    finally:
        conn.close()