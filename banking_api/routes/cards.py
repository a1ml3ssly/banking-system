"""
routes/cards.py

GET  /api/v1/cards                  — list all cards
GET  /api/v1/cards/{id}             — get a single card
GET  /api/v1/cards/account/{id}     — cards belonging to a specific account
GET  /api/v1/cards/client/{id}      — all cards across all accounts of a client
"""

from flask_restx import Namespace, Resource, fields, abort, reqparse

from .. import db
from ..auth import require_auth
from ..utils import serialize_rows, serialize_row, paginate

ns = Namespace('cards', description='Debit and credit card operations')

# ── Swagger models ─────────────────────────────────────────────────────────────
card_model = ns.model('Card', {
    'CardID':      fields.Integer(readonly=True),
    'AccountID':   fields.Integer,
    'CardType':    fields.String(description='debit | credit'),
    'CardNumber':  fields.String(description='Masked — last 4 digits only'),
    'ExpiryDate':  fields.String,
    'Status':      fields.String(description='active | blocked | expired | cancelled'),
    'IssuedAt':    fields.String,
})

page_parser = reqparse.RequestParser()
page_parser.add_argument('page',     type=int, default=1,  location='args')
page_parser.add_argument('per_page', type=int, default=20, location='args')


# ── Resources ─────────────────────────────────────────────────────────────────
@ns.route('/')
class CardList(Resource):

    @require_auth()
    @ns.expect(page_parser)
    @ns.response(503, 'Database unavailable')
    def get(self):
        """List all cards."""
        args     = page_parser.parse_args()
        page     = max(1, args['page'])
        per_page = min(100, max(1, args['per_page']))
        try:
            rows = db.query('SELECT * FROM Cards ORDER BY IssuedAt DESC')
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))
        return paginate(serialize_rows(rows), page, per_page)


@ns.route('/<int:card_id>')
@ns.param('card_id', 'Card ID')
class CardDetail(Resource):

    @require_auth()
    @ns.marshal_with(card_model)
    @ns.response(404, 'Card not found')
    @ns.response(503, 'Database unavailable')
    def get(self, card_id):
        """Get a single card by ID."""
        try:
            row = db.query_one('SELECT * FROM Cards WHERE CardID = %s', (card_id,))
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))
        if not row:
            abort(404, message=f'Card {card_id} not found.')
        return serialize_row(row)


@ns.route('/account/<int:account_id>')
@ns.param('account_id', 'Account ID')
class CardsByAccount(Resource):

    @require_auth()
    @ns.marshal_list_with(card_model)
    @ns.response(404, 'Account not found')
    @ns.response(503, 'Database unavailable')
    def get(self, account_id):
        """List all cards linked to a specific account."""
        try:
            if not db.query_one('SELECT AccountID FROM Accounts WHERE AccountID = %s', (account_id,)):
                abort(404, message=f'Account {account_id} not found.')
            rows = db.query(
                'SELECT * FROM Cards WHERE AccountID = %s ORDER BY IssuedAt DESC', (account_id,)
            )
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))
        return serialize_rows(rows)


@ns.route('/client/<int:client_id>')
@ns.param('client_id', 'Client ID')
class CardsByClient(Resource):

    @require_auth()
    @ns.marshal_list_with(card_model)
    @ns.response(404, 'Client not found')
    @ns.response(503, 'Database unavailable')
    def get(self, client_id):
        """List all cards across all accounts belonging to a client."""
        try:
            if not db.query_one('SELECT ClientID FROM Clients WHERE ClientID = %s', (client_id,)):
                abort(404, message=f'Client {client_id} not found.')
            rows = db.query(
                """
                SELECT c.*
                FROM   Cards    c
                JOIN   Accounts a ON c.AccountID = a.AccountID
                WHERE  a.ClientID = %s
                ORDER BY c.IssuedAt DESC
                """,
                (1,),
            )
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))
        return serialize_rows(rows)
