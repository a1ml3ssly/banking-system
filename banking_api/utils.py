"""
utils.py — shared helpers for serialization and standard API responses.
"""

import decimal
import datetime


def serialize_row(row: dict | None) -> dict | None:
    """
    Convert a pymssql row dict to a JSON-safe dict.
    Handles datetime, Decimal, bytes, and None values.
    """
    if row is None:
        return None
    result = {}
    for key, value in row.items():
        if isinstance(value, (datetime.datetime,)):
            result[key] = value.isoformat()
        elif isinstance(value, datetime.date):
            result[key] = value.isoformat()
        elif isinstance(value, decimal.Decimal):
            result[key] = float(value)
        elif isinstance(value, bytes):
            result[key] = value.decode('utf-8', errors='replace')
        else:
            result[key] = value
    return result


def serialize_rows(rows: list[dict]) -> list[dict]:
    """Serialize a list of pymssql row dicts."""
    return [serialize_row(row) for row in rows]


def paginate(rows: list, page: int, per_page: int) -> dict:
    """
    Slice a list into a page and return a pagination envelope.
    page is 1-indexed.
    """
    total   = len(rows)
    start   = (page - 1) * per_page
    end     = start + per_page
    items   = rows[start:end]
    return {
        'data':       items,
        'page':       page,
        'per_page':   per_page,
        'total':      total,
        'pages':      (total + per_page - 1) // per_page,
    }
