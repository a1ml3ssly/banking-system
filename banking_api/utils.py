from datetime import date, datetime


def serialize(obj):
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    return obj


def serialize_row(row):
    if row is None:
        return None
    return {k: serialize(v) for k, v in row.items()}


def serialize_rows(rows):
    return [serialize_row(r) for r in rows]
