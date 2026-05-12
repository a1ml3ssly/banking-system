"""
auth.py — JWT authentication.

POST /api/v1/token
  Body: { "api_key": "...", "api_secret": "..." }
  Returns: { "access_token": "...", "token_type": "Bearer", "expires_in": 3600, "role": "..." }

Use the returned token in all subsequent requests:
  Authorization: Bearer <access_token>

Roles:
  admin     — full read/write access
  readonly  — GET endpoints only
"""

import datetime
from functools import wraps

import jwt
from flask import request
from flask_restx import Namespace, Resource, fields, abort

from . import config
from . import db

ns = Namespace('auth', description='Authentication — get a JWT token')

# ── Swagger models ─────────────────────────────────────────────────────────────
token_request_model = ns.model('TokenRequest', {
    'api_key':    fields.String(required=True,  description='Your API key'),
    'api_secret': fields.String(required=True,  description='Your API secret'),
})

token_response_model = ns.model('TokenResponse', {
    'access_token': fields.String(description='JWT bearer token'),
    'token_type':   fields.String(description='Always "Bearer"'),
    'expires_in':   fields.Integer(description='Token lifetime in seconds'),
    'role':         fields.String(description='Credential role (admin / readonly)'),
})

# ── Token endpoint ─────────────────────────────────────────────────────────────
@ns.route('/token')
class TokenResource(Resource):
    @ns.expect(token_request_model, validate=True)
    @ns.marshal_with(token_response_model, code=200)
    @ns.response(401, 'Invalid credentials')
    @ns.response(503, 'Database unavailable')
    def post(self):
        """Exchange an API key + secret for a JWT access token."""
        payload = ns.payload
        api_key    = payload.get('api_key', '').strip()
        api_secret = payload.get('api_secret', '').strip()

        try:
            row = db.query_one(
                """
                SELECT Role
                FROM   ApiCredentials
                WHERE  ApiKey    = %s
                  AND  ApiSecret = %s
                  AND  IsActive  = 1
                """,
                (api_key, api_secret),
            )
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))

        if not row:
            abort(401, message='Invalid API key or secret.')

        role = row['Role']
        exp  = datetime.datetime.utcnow() + datetime.timedelta(seconds=config.JWT_EXPIRY_SECONDS)

        token = jwt.encode(
            {'api_key': api_key, 'role': role, 'exp': exp},
            config.JWT_SECRET,
            algorithm='HS256',
        )

        return {
            'access_token': token,
            'token_type':   'Bearer',
            'expires_in':   config.JWT_EXPIRY_SECONDS,
            'role':         role,
        }


# ── Decorator used by all other routes ────────────────────────────────────────
def require_auth(roles: list[str] | None = None):
    """
    Decorator that validates the Bearer JWT on a Flask-RESTX resource method.

    Usage:
        @require_auth()                        # any valid token
        @require_auth(roles=['admin'])         # admin only
        @require_auth(roles=['admin','readonly'])
    """
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            header = request.headers.get('Authorization', '')
            if not header.startswith('Bearer '):
                abort(401, message='Missing Authorization header. Expected: Bearer <token>')

            token = header[7:]
            try:
                decoded = jwt.decode(token, config.JWT_SECRET, algorithms=['HS256'])
            except jwt.ExpiredSignatureError:
                abort(401, message='Token has expired. Request a new one from POST /api/v1/token')
            except jwt.InvalidTokenError:
                abort(401, message='Invalid token.')

            if roles and decoded.get('role') not in roles:
                abort(403, message=f"This action requires one of: {roles}. Your role: {decoded.get('role')}")

            request.current_user = decoded
            return f(*args, **kwargs)
        return wrapper
    return decorator
