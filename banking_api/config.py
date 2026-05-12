"""
config.py — single source of truth for all environment configuration.

To switch between office and home:
  Set DB_PROFILE=office  (on-site LAN)
  Set DB_PROFILE=home    (Tailscale remote)

Copy .env.example to .env and fill in your values.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Database profiles ──────────────────────────────────────────────────────────
_DB_PROFILES = {
    'office': os.getenv('DB_HOST_OFFICE', ''),
    'home':   os.getenv('DB_HOST_HOME', ''),
}

DB_PROFILE  = os.getenv('DB_PROFILE', 'office')
DB_HOST     = _DB_PROFILES.get(DB_PROFILE) or _DB_PROFILES.get('office', '')
DB_PORT     = int(os.getenv('DB_PORT', 1433))
DB_USER     = os.getenv('DB_USER', 'sa')
DB_PASSWORD = os.getenv('DB_PASSWORD', '')
DB_NAME     = os.getenv('DB_NAME', 'BankingDB')

# ── Auth ───────────────────────────────────────────────────────────────────────
JWT_SECRET         = os.getenv('JWT_SECRET', 'change-me-in-production')
JWT_EXPIRY_SECONDS = int(os.getenv('JWT_EXPIRY_SECONDS', 3600))

# ── Server ─────────────────────────────────────────────────────────────────────
API_PORT = int(os.getenv('API_PORT', 5000))
DEBUG    = os.getenv('DEBUG', 'false').lower() == 'true'

# ── Routing ────────────────────────────────────────────────────────────────────
# Full URL structure: gateway / SERVICE_DOMAIN / api / API_VERSION / endpoint
# e.g. http://localhost:8080/banking/api/v1/clients/
SERVICE_DOMAIN = os.getenv('SERVICE_DOMAIN', 'banking')
API_VERSION    = os.getenv('API_VERSION',    'v1')
