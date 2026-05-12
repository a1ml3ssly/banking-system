"""
seed_credentials.py — populate ApiCredentials with the API keys defined in .env.

Usage:
    python seed_credentials.py

Add your keys to .env using this format:

    CRED_1_KEY=bk_live_xxx
    CRED_1_SECRET=bk_secret_xxx
    CRED_1_LABEL=Admin
    CRED_1_ROLE=admin

    CRED_2_KEY=bk_live_yyy
    CRED_2_SECRET=bk_secret_yyy
    CRED_2_LABEL=Analytics readonly
    CRED_2_ROLE=readonly

Add as many CRED_N_* groups as you need.
"""

import os
import sys
import pymssql
from dotenv import load_dotenv

load_dotenv()

# ── DB connection from env ─────────────────────────────────────────────────────
_PROFILES = {
    'office': os.getenv('DB_HOST_OFFICE', ''),
    'home':   os.getenv('DB_HOST_HOME', ''),
}
profile = os.getenv('DB_PROFILE', 'office')
host    = _PROFILES.get(profile) or _PROFILES.get('office', '')

conn_args = dict(
    server   = host,
    port     = int(os.getenv('DB_PORT', 1433)),
    user     = os.getenv('DB_USER', 'sa'),
    password = os.getenv('DB_PASSWORD', ''),
    database = os.getenv('DB_NAME', 'BankingDB'),
)

# ── Collect credentials from env ───────────────────────────────────────────────
credentials = []
n = 1
while True:
    key    = os.getenv(f'CRED_{n}_KEY')
    secret = os.getenv(f'CRED_{n}_SECRET')
    if not key or not secret:
        break
    credentials.append({
        'key':    key,
        'secret': secret,
        'label':  os.getenv(f'CRED_{n}_LABEL', f'Credential {n}'),
        'role':   os.getenv(f'CRED_{n}_ROLE', 'readonly'),
    })
    n += 1

if not credentials:
    print('No credentials found in .env. Add CRED_1_KEY, CRED_1_SECRET, etc.')
    sys.exit(1)

# ── Insert ─────────────────────────────────────────────────────────────────────
try:
    conn = pymssql.connect(**conn_args)
except Exception as exc:
    print(f'Cannot connect to database: {exc}')
    sys.exit(1)

with conn:
    with conn.cursor() as cur:
        for cred in credentials:
            cur.execute(
                """
                IF NOT EXISTS (SELECT 1 FROM ApiCredentials WHERE ApiKey = %s)
                BEGIN
                    INSERT INTO ApiCredentials (ApiKey, ApiSecret, Label, Role)
                    VALUES (%s, %s, %s, %s)
                    PRINT 'Inserted: ' + %s
                END
                ELSE
                BEGIN
                    PRINT 'Already exists: ' + %s
                END
                """,
                (
                    cred['key'],
                    cred['key'], cred['secret'], cred['label'], cred['role'],
                    cred['label'],
                    cred['label'],
                ),
            )
        conn.commit()

print('Done.')
