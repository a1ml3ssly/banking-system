"""
routes/loans.py

GET  /api/v1/loans              — list loans  (paginated)
GET  /api/v1/loans/{id}         — get a single loan + payment history
GET  /api/v1/loans/{id}/payments — list repayment records
"""

from flask_restx import Namespace, Resource, fields, abort, reqparse

from .. import db
from ..auth import require_auth
from ..utils import serialize_rows, serialize_row, paginate

ns = Namespace('loans', description='Loan record operations')

# ── Swagger models ─────────────────────────────────────────────────────────────
loan_model = ns.model('Loan', {
    'LoanID':              fields.Integer(readonly=True),
    'ClientID':            fields.Integer,
    'AccountID':           fields.Integer,
    'LoanType':            fields.String,
    'PrincipalAmount':     fields.Float,
    'InterestRate':        fields.Float,
    'TermMonths':          fields.Integer,
    'MonthlyPayment':      fields.Float,
    'OutstandingBalance':  fields.Float,
    'Status':              fields.String(description='active | paid_off | defaulted | closed'),
    'StartDate':           fields.String,
    'EndDate':             fields.String,
    'CreatedAt':           fields.String,
})

payment_model = ns.model('LoanPayment', {
    'PaymentID':     fields.Integer,
    'LoanID':        fields.Integer,
    'TransactionID': fields.Integer,
    'DueDate':       fields.String,
    'PaidDate':      fields.String,
    'AmountDue':     fields.Float,
    'AmountPaid':    fields.Float,
    'Principal':     fields.Float,
    'Interest':      fields.Float,
    'Penalty':       fields.Float,
    'Status':        fields.String,
})

page_parser = reqparse.RequestParser()
page_parser.add_argument('page',     type=int, default=1,  location='args')
page_parser.add_argument('per_page', type=int, default=20, location='args')
page_parser.add_argument('status',   type=str, default='', location='args',
                         help='Filter by status: active | paid_off | defaulted')


# ── Resources ─────────────────────────────────────────────────────────────────
@ns.route('/')
class LoanList(Resource):

    @require_auth()
    @ns.expect(page_parser)
    @ns.response(503, 'Database unavailable')
    def get(self):
        """List all loans. Optionally filter by status."""
        args     = page_parser.parse_args()
        page     = max(1, args['page'])
        per_page = min(100, max(1, args['per_page']))
        status   = args['status'].strip()

        try:
            if status:
                rows = db.query(
                    'SELECT * FROM Loans WHERE Status = %s ORDER BY StartDate DESC',
                    (status,),
                )
            else:
                rows = db.query('SELECT * FROM Loans ORDER BY StartDate DESC')
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))

        return paginate(serialize_rows(rows), page, per_page)


@ns.route('/<int:loan_id>')
@ns.param('loan_id', 'Loan ID')
class LoanDetail(Resource):

    @require_auth()
    @ns.marshal_with(loan_model)
    @ns.response(404, 'Loan not found')
    @ns.response(503, 'Database unavailable')
    def get(self, loan_id):
        """Get a single loan by ID."""
        try:
            row = db.query_one('SELECT * FROM Loans WHERE LoanID = %s', (loan_id,))
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))
        if not row:
            abort(404, message=f'Loan {loan_id} not found.')
        return serialize_row(row)


@ns.route('/<int:loan_id>/payments')
@ns.param('loan_id', 'Loan ID')
class LoanPayments(Resource):

    @require_auth()
    @ns.marshal_list_with(payment_model)
    @ns.response(404, 'Loan not found')
    @ns.response(503, 'Database unavailable')
    def get(self, loan_id):
        """List all repayment records for a loan."""
        try:
            loan = db.query_one('SELECT LoanID FROM Loans WHERE LoanID = %s', (loan_id,))
            if not loan:
                abort(404, message=f'Loan {loan_id} not found.')
            rows = db.query(
                'SELECT * FROM LoanPayments WHERE LoanID = %s ORDER BY DueDate DESC',
                (loan_id,),
            )
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))
        return serialize_rows(rows)
