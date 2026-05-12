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
    'BranchName': fields.String,
    'Address':    fields.String,
    'City':       fields.String,
    'Country':    fields.String,
    'Phone':      fields.String,
    'ManagerID':  fields.Integer,
    'CreatedAt':  fields.String,
})

branch_input = ns.model('BranchInput', {
    'BranchName': fields.String(required=True,  description='Branch name'),
    'Address':    fields.String(required=True,  description='Street address'),
    'City':       fields.String(required=True,  description='City'),
    'Country':    fields.String(required=False, description='Country', default='Israel'),
    'Phone':      fields.String(required=False, description='Contact phone number'),
    'ManagerID':  fields.Integer(required=False, description='Employee ID of branch manager'),
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
        p = ns.payload
        try:
            row = db.execute_returning(
                """
                INSERT INTO Branches (BranchName, Address, City, Country, Phone, ManagerID)
                OUTPUT INSERTED.*
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    p['BranchName'],
                    p['Address'],
                    p['City'],
                    p.get('Country', 'Israel'),
                    p.get('Phone'),
                    p.get('ManagerID'),
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
