"""
db.py — database connection and query helpers.

Connection is lazy: no attempt is made at startup.
If the DB is unreachable, DatabaseUnavailableError is raised
and the route returns a 503 response — the app never crashes on startup.
"""

import pymssql
from . import config


class DatabaseUnavailableError(Exception):
    """Raised when a DB connection cannot be established."""


def get_connection():
    """Open a fresh pymssql connection. Raises DatabaseUnavailableError on failure."""
    if not config.DB_HOST:
        raise DatabaseUnavailableError(
            f"DB_HOST is empty. Check that DB_PROFILE='{config.DB_PROFILE}' "
            f"matches a host defined in .env (DB_HOST_OFFICE / DB_HOST_HOME)."
        )
    try:
        return pymssql.connect(
            server=config.DB_HOST,
            port=config.DB_PORT,
            user=config.DB_USER,
            password=config.DB_PASSWORD,
            database=config.DB_NAME,
            timeout=5,
            login_timeout=5,
            charset='UTF-8',
        )
    except Exception as exc:
        raise DatabaseUnavailableError(
            f"Cannot connect to {config.DB_HOST}:{config.DB_PORT} "
            f"(profile: {config.DB_PROFILE}) — {exc}"
        ) from exc


def query(sql: str, params: tuple = ()) -> list[dict]:
    """Execute a SELECT statement and return all rows as a list of dicts."""
    with get_connection() as conn:
        with conn.cursor(as_dict=True) as cur:
            cur.execute(sql, params)
            return cur.fetchall() or []


def query_one(sql: str, params: tuple = ()) -> dict | None:
    """Execute a SELECT and return the first row, or None."""
    with get_connection() as conn:
        with conn.cursor(as_dict=True) as cur:
            cur.execute(sql, params)
            return cur.fetchone()


def execute(sql: str, params: tuple = ()) -> int:
    """Execute an INSERT / UPDATE / DELETE. Returns rowcount."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            conn.commit()
            return cur.rowcount


def execute_returning(sql: str, params: tuple = ()) -> dict | None:
    """
    Execute an INSERT that uses an OUTPUT clause and return the inserted row.

    Example SQL:
        INSERT INTO Branches (Name) OUTPUT INSERTED.* VALUES (%s)
    """
    with get_connection() as conn:
        with conn.cursor(as_dict=True) as cur:
            cur.execute(sql, params)
            row = cur.fetchone()  # fetch OUTPUT INSERTED.* before commit clears cursor
            conn.commit()
            return row
