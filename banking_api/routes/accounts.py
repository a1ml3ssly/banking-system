from flask_restx import Namespace, Resource, fields
from banking_api.db import execute, query
from banking_api.utils import serialize_row, serialize_rows

ns = Namespace('accounts', description='Bank accounts')

account_model = ns.model('NewAccount', {
    'ClientID': fields.Integer(required=True, example=1),
    'AccountTypeID': fields.Integer(required=True, example=1),
    'BranchID': fields.Integer(required=True, example=1),
    'AccountNumber': fields.String(required=True, example='ACC-010-001'),
    'Balance': fields.Float(example=0.0),
    'Currency': fields.String(example='ILS'),
})


@ns.route('/')
class AccountList(Resource):
    """
    URL:     /api/accounts/
    Methods: GET, POST

    GET  — no params, no body required.
    POST — JSON body required:
        Required: ClientID (int), AccountTypeID (int), BranchID (int), AccountNumber (str)
        Optional: Balance (float, default 0.0), Currency (str, default 'ILS')
    """

    def get(self):
        """Get all accounts"""
        rows = query('''
                     SELECT a.*, c.FirstName, c.LastName, at.TypeName
                     FROM Accounts a
                              JOIN Clients c ON a.ClientID = c.ClientID
                              JOIN AccountTypes at
                     ON a.AccountTypeID = at.AccountTypeID
                     ORDER BY a.AccountID
                     ''')
        return serialize_rows(rows), 200

    @ns.expect(account_model, validate=True)
    def post(self):
        """Open a new bank account"""
        data = ns.payload
        new_id = execute('''
                         INSERT INTO Accounts (ClientID, AccountTypeID, BranchID, AccountNumber, Balance, Currency)
                         VALUES (%s, %s, %s, %s, %s, %s)
                         ''', (
                             data['ClientID'], data['AccountTypeID'], data['BranchID'],
                             data['AccountNumber'], data.get('Balance', 0.00), data.get('Currency', 'ILS'),
                         ))
        row = query('SELECT * FROM Accounts WHERE AccountID = %s', (new_id,), fetchone=True)
        return serialize_row(row), 201


@ns.route('/<int:account_id>')
@ns.param('account_id', 'The account identifier')
class Account(Resource):
    """
    URL:     /api/accounts/<account_id>
    Methods: GET

    GET — URL param required:
        account_id (int): ID of the account to retrieve.
    No body, no query params, no headers required.
    """

    def get(self, account_id):
        """Get a single account"""
        row = query("""
                    SELECT a.*, c.FirstName, c.LastName, at.TypeName
                    FROM Accounts a
                             JOIN Clients c ON a.ClientID = c.ClientID
                             JOIN AccountTypes at
                    ON a.AccountTypeID = at.AccountTypeID
                    WHERE a.AccountID = %s
                    """, (account_id,), fetchone=True)
        if not row:
            ns.abort(404, f'Account {account_id} not found')
        return serialize_row(row), 200


@ns.route('/<int:account_id>/transactions')
@ns.param('account_id', 'The account identifier')
class AccountTransactions(Resource):
    """
    URL:     /api/accounts/<account_id>/transactions
    Methods: GET

    GET — URL param required:
        account_id (int): ID of the account whose transactions to retrieve.
    No body, no query params, no headers required.
    Returns all transactions where this account is sender or receiver, newest first.
    """

    def get(self, account_id):
        """Get all transactions for an account"""
        rows = query('''
                     SELECT *
                     FROM Transactions
                     WHERE AccountID = %s
                        OR RelatedAccountID = %s
                     ORDER BY TransactionDate DESC
                     ''', (account_id, account_id))
        return serialize_rows(rows), 200
