"""
routes/accounts.py

GET  /api/v1/accounts                      — list accounts  (paginated)
POST /api/v1/accounts                      — create account  [admin]
GET  /api/v1/accounts/{id}                 — get account
GET  /api/v1/accounts/{id}/transactions    — list transactions for this account
"""

from flask_restx import Namespace, Resource, fields, abort, reqparse

from .. import db
from ..auth import require_auth
from ..utils import serialize_rows, serialize_row, paginate

ns = Namespace('accounts', description='Bank account operations')

# ── Swagger models ─────────────────────────────────────────────────────────────
account_model = ns.model('Account', {
    'AccountID':     fields.Integer(readonly=True),
    'AccountNumber': fields.String,
    'ClientID':      fields.Integer,
    'BranchID':      fields.Integer,
    'AccountTypeID': fields.Integer,
    'Balance':       fields.Float,
    'Currency':      fields.String,
    'Status':        fields.String(description='Active | Inactive | Frozen | Closed'),
    'OpenedAt':      fields.String,
    'ClosedAt':      fields.String,
    'UpdatedAt':     fields.String,
})

account_input = ns.model('AccountInput', {
    'ClientID':    fields.Integer(required=True,  description='Owner client ID'),
    'BranchID':   fields.Integer(required=True,  description='Branch ID'),
    'AccountType': fields.String(required=True,  description='TypeCode or TypeName from AccountTypes (e.g. Checking, Savings)'),
    'Currency':    fields.String(required=False, description='3-letter ISO code', default='ILS'),
})

transaction_model = ns.model('AccountTransaction', {
    'TransactionID':   fields.Integer,
    'TransactionType': fields.String,
    'Amount':          fields.Float,
    'Currency':        fields.String,
    'Description':     fields.String,
    'ReferenceNumber': fields.String,
    'TransactionDate': fields.String,
    'Status':          fields.String,
})

page_parser = reqparse.RequestParser()
page_parser.add_argument('page',     type=int, default=1,  location='args')
page_parser.add_argument('per_page', type=int, default=20, location='args')

txn_parser = reqparse.RequestParser()
txn_parser.add_argument('page',     type=int, default=1,  location='args')
txn_parser.add_argument('per_page', type=int, default=50, location='args')


# ── Resources ─────────────────────────────────────────────────────────────────
@ns.route('/')
class AccountList(Resource):

    @require_auth()
    @ns.expect(page_parser)
    @ns.response(503, 'Database unavailable')
    def get(self):
        """List all accounts with pagination."""
        args     = page_parser.parse_args()
        page     = max(1, args['page'])
        per_page = min(100, max(1, args['per_page']))
        try:
            rows = db.query('SELECT * FROM Accounts ORDER BY OpenedAt DESC')
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))
        return paginate(serialize_rows(rows), page, per_page)

    @require_auth(roles=['admin'])
    @ns.expect(account_input, validate=True)
    @ns.marshal_with(account_model, code=201)
    @ns.response(400, 'Validation error')
    @ns.response(503, 'Database unavailable')
    def post(self):
        """Create a new account. [admin only]"""
        p = ns.payload
        try:
            # Validate client + branch exist
            if not db.query_one('SELECT ClientID FROM Clients WHERE ClientID = %s', (p['ClientID'],)):
                abort(400, message=f"Client {p['ClientID']} does not exist.")
            if not db.query_one('SELECT BranchID FROM Branches WHERE BranchID = %s', (p['BranchID'],)):
                abort(400, message=f"Branch {p['BranchID']} does not exist.")

            # Resolve AccountTypeID from TypeCode, TypeName, or raw integer ID
            at = db.query_one(
                'SELECT AccountTypeID FROM AccountTypes WHERE TypeCode = %s OR TypeName = %s OR CAST(AccountTypeID AS NVARCHAR) = %s',
                (p['AccountType'], p['AccountType'], p['AccountType']),
            )
            if not at:
                valid = db.query('SELECT TypeCode, TypeName FROM AccountTypes WHERE IsActive = 1')
                opts = ', '.join(f"{r['TypeCode']}/{r['TypeName']}" for r in valid)
                abort(400, message=f"Unknown account type '{p['AccountType']}'. Valid options: {opts}")

            # Generate an account number
            import random, string
            acct_num = 'ACC' + ''.join(random.choices(string.digits, k=10))

            row = db.execute_returning(
                """
                INSERT INTO Accounts (AccountNumber, ClientID, BranchID, AccountTypeID, Balance, Currency, Status)
                OUTPUT INSERTED.*
                VALUES (%s, %s, %s, %s, 0.00, %s, 'Active')
                """,
                (acct_num, p['ClientID'], p['BranchID'], at['AccountTypeID'], p.get('Currency', 'ILS')),
            )
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))
        return serialize_row(row), 201


@ns.route('/<int:account_id>')
@ns.param('account_id', 'Account ID')
class AccountDetail(Resource):

    @require_auth()
    @ns.marshal_with(account_model)
    @ns.response(404, 'Account not found')
    @ns.response(503, 'Database unavailable')
    def get(self, account_id):
        """Get a single account by ID."""
        try:
            row = db.query_one('SELECT * FROM Accounts WHERE AccountID = %s', (account_id,))
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))
        if not row:
            abort(404, message=f'Account {account_id} not found.')
        return serialize_row(row)


@ns.route('/<int:account_id>/transactions')
@ns.param('account_id', 'Account ID')
class AccountTransactions(Resource):

    @require_auth()
    @ns.expect(txn_parser)
    @ns.response(404, 'Account not found')
    @ns.response(503, 'Database unavailable')
    def get(self, account_id):
        """List transactions for a specific account, newest first."""
        args     = txn_parser.parse_args()
        page     = max(1, args['page'])
        per_page = min(200, max(1, args['per_page']))
        try:
            acct = db.query_one('SELECT AccountID FROM Accounts WHERE AccountID = %s', (account_id,))
            if not acct:
                abort(404, message=f'Account {account_id} not found.')
            rows = db.query(
                'SELECT * FROM Transactions WHERE AccountID = %s ORDER BY TransactionDate DESC',
                (account_id,),
            )
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))
        return paginate(serialize_rows(rows), page, per_page)
