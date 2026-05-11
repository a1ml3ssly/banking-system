from flask_restx import Namespace, Resource, fields

from db import execute, query
from utils import serialize_rows

ns = Namespace('transactions', description='Deposits, withdrawals & transfers')

deposit_model = ns.model('DepositWithdrawal', {
    'AccountID':   fields.Integer(required=True, example=1),
    'Amount':      fields.Float(required=True,   example=1000.00),
    'Description': fields.String(example='Cash deposit'),
    'Type':        fields.String(required=True,  enum=['Deposit', 'Withdrawal'], example='Deposit'),
})

transfer_model = ns.model('Transfer', {
    'FromAccountID': fields.Integer(required=True, example=1),
    'ToAccountID':   fields.Integer(required=True, example=3),
    'Amount':        fields.Float(required=True,   example=500.00),
    'Description':   fields.String(example='Rent payment'),
})


@ns.route('/')
class TransactionList(Resource):
    def get(self):
        """Get all transactions (most recent first)"""
        rows = query('''
            SELECT TOP 100 t.*, a.AccountNumber
            FROM Transactions t
            JOIN Accounts a ON t.AccountID = a.AccountID
            ORDER BY t.TransactionDate DESC
        ''')
        return serialize_rows(rows), 200


@ns.route('/deposit-withdrawal')
class DepositWithdrawal(Resource):
    @ns.expect(deposit_model, validate=True)
    def post(self):
        """Perform a deposit or withdrawal"""
        data = ns.payload
        account = query('SELECT * FROM Accounts WHERE AccountID = %s', (data['AccountID'],), fetchone=True)
        if not account:
            ns.abort(404, 'Account not found')

        amount  = float(data['Amount'])
        tx_type = data['Type']

        if tx_type == 'Withdrawal':
            if account['Balance'] < amount:
                ns.abort(400, 'Insufficient funds')
            new_balance = account['Balance'] - amount
        else:
            new_balance = account['Balance'] + amount

        execute('UPDATE Accounts SET Balance = %s WHERE AccountID = %s', (new_balance, data['AccountID']))
        new_id = execute('''
            INSERT INTO Transactions (AccountID, TransactionType, Amount, Description, Status)
            VALUES (%s, %s, %s, %s, 'Completed')
        ''', (data['AccountID'], tx_type, amount, data.get('Description', '')))

        return {'message': f'{tx_type} successful', 'transaction_id': new_id, 'new_balance': new_balance}, 201


@ns.route('/transfer')
class Transfer(Resource):
    @ns.expect(transfer_model, validate=True)
    def post(self):
        """Transfer funds between two accounts"""
        data     = ns.payload
        amount   = float(data['Amount'])
        from_acc = query('SELECT * FROM Accounts WHERE AccountID = %s', (data['FromAccountID'],), fetchone=True)
        to_acc   = query('SELECT * FROM Accounts WHERE AccountID = %s', (data['ToAccountID'],),   fetchone=True)

        if not from_acc:
            ns.abort(404, 'Source account not found')
        if not to_acc:
            ns.abort(404, 'Destination account not found')
        if from_acc['Balance'] < amount:
            ns.abort(400, 'Insufficient funds')

        execute('UPDATE Accounts SET Balance = Balance - %s WHERE AccountID = %s', (amount, data['FromAccountID']))
        execute('UPDATE Accounts SET Balance = Balance + %s WHERE AccountID = %s', (amount, data['ToAccountID']))

        desc   = data.get('Description', 'Transfer')
        tx_out = execute('''
            INSERT INTO Transactions (AccountID, RelatedAccountID, TransactionType, Amount, Description, Status)
            VALUES (%s, %s, 'Transfer', %s, %s, 'Completed')
        ''', (data['FromAccountID'], data['ToAccountID'], amount, desc))
        execute('''
            INSERT INTO Transactions (AccountID, RelatedAccountID, TransactionType, Amount, Description, Status)
            VALUES (%s, %s, 'Transfer', %s, %s, 'Completed')
        ''', (data['ToAccountID'], data['FromAccountID'], amount, f'Received: {desc}'))

        return {'message': 'Transfer successful', 'transaction_id': tx_out, 'amount': amount}, 201
