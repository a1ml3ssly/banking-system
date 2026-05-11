from flask_restx import Namespace, Resource

from db import query
from utils import serialize_row, serialize_rows

ns = Namespace('branches', description='Bank branches')


@ns.route('/')
class BranchList(Resource):
    def get(self):
        """Get all branches"""
        rows = query('SELECT * FROM Branches ORDER BY BranchID')
        return serialize_rows(rows), 200


@ns.route('/<int:branch_id>')
@ns.param('branch_id', 'The branch identifier')
class Branch(Resource):
    def get(self, branch_id):
        """Get a single branch by ID"""
        row = query('SELECT * FROM Branches WHERE BranchID = %s', (branch_id,), fetchone=True)
        if not row:
            ns.abort(404, f'Branch {branch_id} not found')
        return serialize_row(row), 200
