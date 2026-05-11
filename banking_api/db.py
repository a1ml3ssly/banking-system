import pymssql
import os
from dotenv import load_dotenv

load_dotenv()

def get_connection():
    return pymssql.connect(
        server=os.getenv('DB_HOST', 'localhost'),
        port=int(os.getenv('DB_PORT', 1433)),
        user=os.getenv('DB_USER', 'sa'),
        password=os.getenv('DB_PASSWORD', ''),
        database=os.getenv('DB_NAME', 'BankingDB')
    )

def query(sql, params=None, fetchone=False):
    """Execute a SELECT query and return results as list of dicts."""
    conn = get_connection()
    try:
        cursor = conn.cursor(as_dict=True)
        cursor.execute(sql, params or ())
        if fetchone:
            return cursor.fetchone()
        return cursor.fetchall()
    finally:
        conn.close()

def execute(sql, params=None):
    """Execute INSERT/UPDATE/DELETE and return last inserted ID if available."""
    conn = get_connection()
    try:
        cursor = conn.cursor()
        cursor.execute(sql, params or ())
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()
