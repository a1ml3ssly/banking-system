from flask_restx import Namespace, Resource

from db import query
from utils import serialize_row, serialize_rows

ns = Namespace('credit-cards', description='Credit card operations')


@ns.route('/')
class CreditCardList(Resource):
    def get(self):
        """Get all credit cards"""
        rows = query('''
            SELECT cc.*, c.FirstName, c.LastName
            FROM CreditCards cc
            JOIN Clients c ON cc.ClientID = c.ClientID
            ORDER BY cc.CardID
        ''')
        return serialize_rows(rows), 200


@ns.route('/<int:card_id>')
@ns.param('card_id', 'The card identifier')
class CreditCard(Resource):
    def get(self, card_id):
        """Get a credit card with recent transactions"""
        card = query('''
            SELECT cc.*, c.FirstName, c.LastName
            FROM CreditCards cc
            JOIN Clients c ON cc.ClientID = c.ClientID
            WHERE cc.CardID = %s
        ''', (card_id,), fetchone=True)
        if not card:
            ns.abort(404, f'Card {card_id} not found')
        transactions = query('SELECT TOP 20 * FROM CreditCardTransactions WHERE CardID = %s ORDER BY TransactionDate DESC', (card_id,))
        billing      = query('SELECT TOP 3 * FROM BillingCycles WHERE CardID = %s ORDER BY CycleEndDate DESC', (card_id,))
        return {'card': serialize_row(card), 'transactions': serialize_rows(transactions), 'billing': serialize_rows(billing)}, 200


@ns.route('/client/<int:client_id>')
@ns.param('client_id', 'The client identifier')
class ClientCreditCards(Resource):
    def get(self, client_id):
        """Get all credit cards for a client"""
        rows = query('SELECT * FROM CreditCards WHERE ClientID = %s', (client_id,))
        return serialize_rows(rows), 200
