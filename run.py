"""
run.py — local development entry point.

Usage:
    python run.py

Swagger UI will be at: http://127.0.0.1:5000/docs

Make sure you have a .env file (copy from .env.example and fill in your values).
The app starts even if the database is unreachable — endpoints return 503 until the DB is up.
"""

from banking_api import create_app
from banking_api import config

app = create_app()

if __name__ == '__main__':
    prefix = f'/{config.SERVICE_DOMAIN}/api/{config.API_VERSION}'
    print(f'\n  Banking API  →  http://0.0.0.0:{config.API_PORT}{prefix}')
    print(f'  Swagger UI   →  http://0.0.0.0:{config.API_PORT}/docs')
    print(f'  DB profile   →  {config.DB_PROFILE} ({config.DB_HOST}:{config.DB_PORT})\n')
    app.run(host='0.0.0.0', port=config.API_PORT, debug=config.DEBUG)
