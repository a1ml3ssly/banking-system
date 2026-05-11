import os
import time

import jwt
from flask import Blueprint, jsonify, request
from werkzeug.security import check_password_hash

from db import execute, query

auth_bp = Blueprint('auth', __name__)

JWT_SECRET = os.getenv('JWT_SECRET', 'BankingDemoSecret2024!')
JWT_ALGORITHM = 'HS256'
JWT_EXPIRY_SECONDS = int(os.getenv('JWT_EXPIRY_SECONDS', 3600))

ROLE_TO_POLICY = {
    'admin':    'admin-policy',
    'readonly': 'readonly-policy',
}


@auth_bp.route('/token', methods=['POST'])
def get_token():
    """Exchange API key + secret for a short-lived JWT token."""
    data = request.get_json(silent=True)
    if not data or not data.get('key') or not data.get('secret'):
        return jsonify({'error': 'key and secret are required'}), 400

    credential = query(
        'SELECT * FROM ApiCredentials WHERE ApiKey = %s AND IsActive = 1',
        (data['key'],), fetchone=True,
    )
    if not credential:
        return jsonify({'error': 'Invalid key or secret'}), 401
    if not check_password_hash(credential['ApiSecretHash'], data['secret']):
        return jsonify({'error': 'Invalid key or secret'}), 401

    now = int(time.time())
    policy = ROLE_TO_POLICY.get(credential['Role'], 'readonly-policy')
    payload = {
        'sub':  credential['ApiKey'],
        'pol':  policy,
        'role': credential['Role'],
        'name': credential['Name'],
        'iat':  now,
        'exp':  now + JWT_EXPIRY_SECONDS,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    execute('UPDATE ApiCredentials SET LastUsedAt = GETDATE() WHERE CredentialID = %s', (credential['CredentialID'],))
    return jsonify({
        'access_token': token,
        'token_type':   'Bearer',
        'expires_in':   JWT_EXPIRY_SECONDS,
        'role':         credential['Role'],
    }), 200
