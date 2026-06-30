from contextlib import contextmanager
from typing import Generator

import psycopg

from ..core.config import settings

@contextmanager
def get_users_connection() -> Generator[psycopg.Connection, None, None]:
    conn = psycopg.connect(settings.users_dsn)
    try:
        yield conn
    finally:
        conn.close()
