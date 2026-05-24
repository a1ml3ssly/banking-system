"""
routes/branches.py

GET  /api/v1/branches          — list all branches
GET  /api/v1/branches/{id}     — get a single branch
POST /api/v1/branches          — create a branch  [admin]
"""

from flask_restx import Namespace, Resource, fields, abort

from .. import db
from ..auth import require_auth
from ..utils import serialize_rows, serialize_row

ns = Namespace('branches', description='Bank branch operations')

# ── Swagger models ─────────────────────────────────────────────────────────────
branch_model = ns.model('Branch', {
    'BranchID':   fields.Integer(readonly=True),
    'BranchCode': fields.String,
    'BranchName': fields.String,
    'Address':    fields.String,
    'City':       fields.String,
    'Country':    fields.String,
    'Phone':      fields.String,
    'Email':      fields.String,
    'IsActive':   fields.Boolean,
    'CreatedAt':  fields.String,
})

branch_input = ns.model('BranchInput', {
    'BranchName': fields.String(required=True,  description='Branch name'),
    'Address':    fields.String(required=True,  description='Street address'),
    'City':       fields.String(required=True,  description='City'),
    'Country':    fields.String(required=False, description='Country', default='Israel'),
    'Phone':      fields.String(required=False, description='Contact phone number'),
    'Email':      fields.String(required=False, description='Branch email address'),
})


# ── Resources ─────────────────────────────────────────────────────────────────
@ns.route('/')
class BranchList(Resource):

    @require_auth()
    @ns.marshal_list_with(branch_model)
    @ns.response(503, 'Database unavailable')
    def get(self):
        """List all branches."""
        try:
            rows = db.query('SELECT * FROM Branches ORDER BY BranchName')
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))
        return serialize_rows(rows)

    @require_auth(roles=['admin'])
    @ns.expect(branch_input, validate=True)
    @ns.marshal_with(branch_model, code=201)
    @ns.response(400, 'Validation error')
    @ns.response(503, 'Database unavailable')
    def post(self):
        """Create a new branch. [admin only]"""
        import random, string as _string
        p = ns.payload
        branch_code = (p['City'][:3].upper() +
                       ''.join(random.choices(_string.digits, k=3)))
        try:
            row = db.execute_returning(
                """
                INSERT INTO Branches (BranchCode, BranchName, Address, City, Country, Phone, Email, IsActive)
                OUTPUT INSERTED.*
                VALUES (%s, %s, %s, %s, %s, %s, %s, 1)
                """,
                (
                    branch_code,
                    p['BranchName'],
                    p['Address'],
                    p['City'],
                    p.get('Country', 'Israel'),
                    p.get('Phone'),
                    p.get('Email'),
                ),
            )
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))
        return serialize_row(row), 201


@ns.route('/<int:branch_id>')
@ns.param('branch_id', 'Branch ID')
class BranchDetail(Resource):

    @require_auth()
    @ns.marshal_with(branch_model)
    @ns.response(404, 'Branch not found')
    @ns.response(503, 'Database unavailable')
    def get(self, branch_id):
        """Get a single branch by ID."""
        try:
            row = db.query_one('SELECT * FROM Branches WHERE BranchID = %s', (branch_id,))
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))
        if not row:
            abort(404, message=f'Branch {branch_id} not found.')
        return serialize_row(row)
