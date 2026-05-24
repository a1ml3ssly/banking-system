"""
routes/transactions.py

GET  /api/v1/transactions              — list transactions  (paginated)
GET  /api/v1/transactions/{id}         — get a single transaction
POST /api/v1/transactions/deposit      — deposit to an account  [admin]
POST /api/v1/transactions/withdrawal   — withdraw from an account  [admin]
POST /api/v1/transactions/transfer     — transfer between two accounts  [admin]
"""

import uuid
from flask_restx import Namespace, Resource, fields, abort, reqparse

from .. import db
from ..auth import require_auth
from ..utils import serialize_rows, serialize_row, paginate

ns = Namespace('transactions', description='Transaction operations')

# ── Swagger models ─────────────────────────────────────────────────────────────
transaction_model = ns.model('Transaction', {
    'TransactionID':   fields.Integer(readonly=True),
    'AccountID':       fields.Integer,
    'TransactionType': fields.String,
    'Amount':          fields.Float,
    'Currency':        fields.String,
    'Description':     fields.String,
    'ReferenceNumber': fields.String,
    'TransactionDate': fields.String,
    'Status':          fields.String,
})

deposit_input = ns.model('DepositInput', {
    'account_id':  fields.Integer(required=True,  description='Target account ID'),
    'amount':      fields.Float(required=True,    description='Amount to deposit (positive)'),
    'currency':    fields.String(required=False,  description='Currency code', default='ILS'),
    'description': fields.String(required=False,  description='Optional note'),
})

withdrawal_input = ns.model('WithdrawalInput', {
    'account_id':  fields.Integer(required=True,  description='Source account ID'),
    'amount':      fields.Float(required=True,    description='Amount to withdraw (positive)'),
    'currency':    fields.String(required=False,  description='Currency code', default='ILS'),
    'description': fields.String(required=False,  description='Optional note'),
})

transfer_input = ns.model('TransferInput', {
    'from_account_id': fields.Integer(required=True,  description='Source account ID'),
    'to_account_id':   fields.Integer(required=True,  description='Destination account ID'),
    'amount':          fields.Float(required=True,    description='Amount to transfer (positive)'),
    'currency':        fields.String(required=False,  description='Currency code', default='ILS'),
    'description':     fields.String(required=False,  description='Optional note'),
})

page_parser = reqparse.RequestParser()
page_parser.add_argument('page',     type=int, default=1,  location='args')
page_parser.add_argument('per_page', type=int, default=50, location='args')


# ── Helpers ────────────────────────────────────────────────────────────────────
def _ref() -> str:
    """Generate a unique reference number."""
    return 'TXN-' + str(uuid.uuid4()).upper()[:12]


def _get_active_account(account_id: int) -> dict:
    """Return account row or abort with 404/400."""
    row = db.query_one(
        "SELECT AccountID, Balance, Currency, Status FROM Accounts WHERE AccountID = %s",
        (account_id,),
    )
    if not row:
        abort(404, message=f'Account {account_id} not found.')
    if row['Status'].lower() != 'active':
        abort(400, message=f'Account {account_id} is not active (status: {row["Status"]}).')
    return row


# ── Resources ─────────────────────────────────────────────────────────────────
@ns.route('/')
class TransactionList(Resource):

    @require_auth()
    @ns.expect(page_parser)
    @ns.response(503, 'Database unavailable')
    def get(self):
        """List all transactions, newest first."""
        args     = page_parser.parse_args()
        page     = max(1, args['page'])
        per_page = min(200, max(1, args['per_page']))
        try:
            rows = db.query('SELECT * FROM Transactions ORDER BY TransactionDate DESC')
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))
        return paginate(serialize_rows(rows), page, per_page)


@ns.route('/<int:transaction_id>')
@ns.param('transaction_id', 'Transaction ID')
class TransactionDetail(Resource):

    @require_auth()
    @ns.marshal_with(transaction_model)
    @ns.response(404, 'Transaction not found')
    @ns.response(503, 'Database unavailable')
    def get(self, transaction_id):
        """Get a single transaction by ID."""
        try:
            row = db.query_one(
                'SELECT * FROM Transactions WHERE TransactionID = %s', (transaction_id,)
            )
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))
        if not row:
            abort(404, message=f'Transaction {transaction_id} not found.')
        return serialize_row(row)


@ns.route('/deposit')
class Deposit(Resource):

    @require_auth(roles=['admin'])
    @ns.expect(deposit_input, validate=True)
    @ns.marshal_with(transaction_model, code=201)
    @ns.response(400, 'Invalid account or amount')
    @ns.response(503, 'Database unavailable')
    def post(self):
        """Deposit funds into an account. [admin only]"""
        p = ns.payload
        amount = float(p['amount'])
        if amount <= 0:
            abort(400, message='Amount must be greater than zero.')

        try:
            acct = _get_active_account(p['account_id'])

            # Insert transaction record
            ref = _ref()
            row = db.execute_returning(
                """
                INSERT INTO Transactions
                    (AccountID, TransactionType, Amount, Currency, Description, ReferenceNumber, Status)
                OUTPUT INSERTED.*
                VALUES (%s, 'credit', %s, %s, %s, %s, 'completed')
                """,
                (
                    acct['AccountID'],
                    amount,
                    p.get('currency', acct['Currency']),
                    p.get('description', 'Deposit'),
                    ref,
                ),
            )

            # Update account balance
            db.execute(
                'UPDATE Accounts SET Balance = Balance + %s, UpdatedAt = GETDATE() WHERE AccountID = %s',
                (amount, acct['AccountID']),
            )
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))

        return serialize_row(row), 201


@ns.route('/withdrawal')
class Withdrawal(Resource):

    @require_auth(roles=['admin'])
    @ns.expect(withdrawal_input, validate=True)
    @ns.marshal_with(transaction_model, code=201)
    @ns.response(400, 'Insufficient funds or invalid account')
    @ns.response(503, 'Database unavailable')
    def post(self):
        """Withdraw funds from an account. [admin only]"""
        p = ns.payload
        amount = float(p['amount'])
        if amount <= 0:
            abort(400, message='Amount must be greater than zero.')

        try:
            acct = _get_active_account(p['account_id'])
            if float(acct['Balance']) < amount:
                abort(400, message=(
                    f'Insufficient funds. Available: {acct["Balance"]}, Requested: {amount}'
                ))

            ref = _ref()
            row = db.execute_returning(
                """
                INSERT INTO Transactions
                    (AccountID, TransactionType, Amount, Currency, Description, ReferenceNumber, Status)
                OUTPUT INSERTED.*
                VALUES (%s, 'debit', %s, %s, %s, %s, 'completed')
                """,
                (
                    acct['AccountID'],
                    amount,
                    p.get('currency', acct['Currency']),
                    p.get('description', 'Withdrawal'),
                    ref,
                ),
            )

            db.execute(
                'UPDATE Accounts SET Balance = Balance - %s, UpdatedAt = GETDATE() WHERE AccountID = %s',
                (amount, acct['AccountID']),
            )
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))

        return serialize_row(row), 201


@ns.route('/transfer')
class Transfer(Resource):

    @require_auth(roles=['admin'])
    @ns.expect(transfer_input, validate=True)
    @ns.response(201, 'Transfer successful')
    @ns.response(400, 'Insufficient funds or invalid accounts')
    @ns.response(503, 'Database unavailable')
    def post(self):
        """Transfer funds between two accounts. [admin only]"""
        p = ns.payload
        amount = float(p['amount'])
        if amount <= 0:
            abort(400, message='Amount must be greater than zero.')
        if p['from_account_id'] == p['to_account_id']:
            abort(400, message='Source and destination accounts must be different.')

        try:
            from_acct = _get_active_account(p['from_account_id'])
            to_acct   = _get_active_account(p['to_account_id'])

            if float(from_acct['Balance']) < amount:
                abort(400, message=(
                    f'Insufficient funds. Available: {from_acct["Balance"]}, Requested: {amount}'
                ))

            currency = p.get('currency', from_acct['Currency'])
            note     = p.get('description', 'Transfer')
            ref      = _ref()

            # Debit source
            debit_row = db.execute_returning(
                """
                INSERT INTO Transactions
                    (AccountID, TransactionType, Amount, Currency, Description, ReferenceNumber, Status)
                OUTPUT INSERTED.*
                VALUES (%s, 'debit', %s, %s, %s, %s, 'completed')
                """,
                (from_acct['AccountID'], amount, currency, f'{note} → Acct {to_acct["AccountID"]}', ref),
            )
            db.execute(
                'UPDATE Accounts SET Balance = Balance - %s, UpdatedAt = GETDATE() WHERE AccountID = %s',
                (amount, from_acct['AccountID']),
            )

            # Credit destination
            db.execute_returning(
                """
                INSERT INTO Transactions
                    (AccountID, TransactionType, Amount, Currency, Description, ReferenceNumber, Status)
                OUTPUT INSERTED.*
                VALUES (%s, 'credit', %s, %s, %s, %s, 'completed')
                """,
                (to_acct['AccountID'], amount, currency, f'{note} ← Acct {from_acct["AccountID"]}', ref),
            )
            db.execute(
                'UPDATE Accounts SET Balance = Balance + %s, UpdatedAt = GETDATE() WHERE AccountID = %s',
                (amount, to_acct['AccountID']),
            )

        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))

        return {
            'message':        'Transfer completed successfully.',
            'reference':      ref,
            'amount':         amount,
            'from_account_id': p['from_account_id'],
            'to_account_id':  p['to_account_id'],
        }, 201
