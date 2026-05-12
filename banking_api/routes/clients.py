"""
routes/clients.py

GET  /api/v1/clients                   — list clients  (paginated)
POST /api/v1/clients                   — create client  [admin]
GET  /api/v1/clients/{id}              — get client
GET  /api/v1/clients/{id}/accounts     — list accounts owned by client
GET  /api/v1/clients/{id}/summary      — financial snapshot
"""

from flask_restx import Namespace, Resource, fields, abort, reqparse

from .. import db
from ..auth import require_auth
from ..utils import serialize_rows, serialize_row, paginate

ns = Namespace('clients', description='Client (customer) operations')

# ── Swagger models ─────────────────────────────────────────────────────────────
client_model = ns.model('Client', {
    'ClientID':    fields.Integer(readonly=True),
    'FirstName':   fields.String,
    'LastName':    fields.String,
    'Email':       fields.String,
    'Phone':       fields.String,
    'DateOfBirth': fields.String,
    'Address':     fields.String,
    'ClientType':  fields.String(description='individual | business'),
    'CreatedAt':   fields.String,
})

client_input = ns.model('ClientInput', {
    'FirstName':   fields.String(required=True),
    'LastName':    fields.String(required=True),
    'Email':       fields.String(required=True),
    'Phone':       fields.String(required=False),
    'DateOfBirth': fields.String(required=False, description='YYYY-MM-DD'),
    'Address':     fields.String(required=False),
    'ClientType':  fields.String(required=False, default='individual',
                                 description='individual | business'),
})

account_model = ns.model('ClientAccount', {
    'AccountID':     fields.Integer,
    'AccountNumber': fields.String,
    'AccountType':   fields.String,
    'Balance':       fields.Float,
    'Currency':      fields.String,
    'Status':        fields.String,
    'OpenedAt':      fields.String,
})

summary_model = ns.model('ClientSummary', {
    'ClientID':       fields.Integer,
    'FullName':       fields.String,
    'TotalAccounts':  fields.Integer,
    'TotalBalance':   fields.Float,
    'ActiveLoans':    fields.Integer,
    'OpenTickets':    fields.Integer,
})

# ── Pagination parser ──────────────────────────────────────────────────────────
page_parser = reqparse.RequestParser()
page_parser.add_argument('page',     type=int, default=1,  location='args', help='Page number (1-indexed)')
page_parser.add_argument('per_page', type=int, default=20, location='args', help='Items per page (max 100)')
page_parser.add_argument('search',   type=str, default='', location='args', help='Filter by name or email')


# ── Resources ─────────────────────────────────────────────────────────────────
@ns.route('/')
class ClientList(Resource):

    @require_auth()
    @ns.expect(page_parser)
    @ns.response(200, 'Success')
    @ns.response(503, 'Database unavailable')
    def get(self):
        """List clients with optional search and pagination."""
        args     = page_parser.parse_args()
        page     = max(1, args['page'])
        per_page = min(100, max(1, args['per_page']))
        search   = args['search'].strip()

        try:
            if search:
                rows = db.query(
                    """
                    SELECT * FROM Clients
                    WHERE  FirstName LIKE %s
                        OR LastName  LIKE %s
                        OR Email     LIKE %s
                    ORDER BY LastName, FirstName
                    """,
                    (f'%{search}%', f'%{search}%', f'%{search}%'),
                )
            else:
                rows = db.query('SELECT * FROM Clients ORDER BY LastName, FirstName')
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))

        return paginate(serialize_rows(rows), page, per_page)

    @require_auth(roles=['admin'])
    @ns.expect(client_input, validate=True)
    @ns.marshal_with(client_model, code=201)
    @ns.response(400, 'Validation error')
    @ns.response(503, 'Database unavailable')
    def post(self):
        """Create a new client. [admin only]"""
        p = ns.payload
        try:
            # Check for duplicate email
            existing = db.query_one(
                'SELECT ClientID FROM Clients WHERE Email = %s', (p['Email'],)
            )
            if existing:
                abort(400, message=f"A client with email '{p['Email']}' already exists.")

            row = db.execute_returning(
                """
                INSERT INTO Clients (FirstName, LastName, Email, Phone, DateOfBirth, Address, ClientType)
                OUTPUT INSERTED.*
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    p['FirstName'],
                    p['LastName'],
                    p['Email'],
                    p.get('Phone'),
                    p.get('DateOfBirth'),
                    p.get('Address'),
                    p.get('ClientType', 'individual'),
                ),
            )
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))
        return serialize_row(row), 201


@ns.route('/<int:client_id>')
@ns.param('client_id', 'Client ID')
class ClientDetail(Resource):

    @require_auth()
    @ns.marshal_with(client_model)
    @ns.response(404, 'Client not found')
    @ns.response(503, 'Database unavailable')
    def get(self, client_id):
        """Get a single client by ID."""
        try:
            row = db.query_one('SELECT * FROM Clients WHERE ClientID = %s', (client_id,))
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))
        if not row:
            abort(404, message=f'Client {client_id} not found.')
        return serialize_row(row)


@ns.route('/<int:client_id>/accounts')
@ns.param('client_id', 'Client ID')
class ClientAccounts(Resource):

    @require_auth()
    @ns.marshal_list_with(account_model)
    @ns.response(404, 'Client not found')
    @ns.response(503, 'Database unavailable')
    def get(self, client_id):
        """List all accounts belonging to a client."""
        try:
            client = db.query_one('SELECT ClientID FROM Clients WHERE ClientID = %s', (client_id,))
            if not client:
                abort(404, message=f'Client {client_id} not found.')
            rows = db.query(
                'SELECT * FROM Accounts WHERE ClientID = %s ORDER BY OpenedAt DESC',
                (client_id,),
            )
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))
        return serialize_rows(rows)


@ns.route('/<int:client_id>/summary')
@ns.param('client_id', 'Client ID')
class ClientSummary(Resource):

    @require_auth()
    @ns.marshal_with(summary_model)
    @ns.response(404, 'Client not found')
    @ns.response(503, 'Database unavailable')
    def get(self, client_id):
        """Financial snapshot: total balance, active loans, open tickets."""
        try:
            client = db.query_one(
                "SELECT ClientID, FirstName + ' ' + LastName AS FullName FROM Clients WHERE ClientID = %s",
                (client_id,),
            )
            if not client:
                abort(404, message=f'Client {client_id} not found.')

            totals = db.query_one(
                """
                SELECT
                    COUNT(*)        AS TotalAccounts,
                    ISNULL(SUM(Balance), 0) AS TotalBalance
                FROM Accounts
                WHERE ClientID = %s AND Status = 'active'
                """,
                (client_id,),
            )
            loans = db.query_one(
                "SELECT COUNT(*) AS ActiveLoans FROM Loans l "
                "JOIN Accounts a ON l.AccountID = a.AccountID "
                "WHERE a.ClientID = %s AND l.Status = 'active'",
                (client_id,),
            )
            tickets = db.query_one(
                "SELECT COUNT(*) AS OpenTickets FROM SupportTickets "
                "WHERE ClientID = %s AND Status = 'open'",
                (client_id,),
            )
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))

        return serialize_row({
            'ClientID':      client_id,
            'FullName':      client['FullName'],
            'TotalAccounts': totals['TotalAccounts'],
            'TotalBalance':  totals['TotalBalance'],
            'ActiveLoans':   loans['ActiveLoans'],
            'OpenTickets':   tickets['OpenTickets'],
        })
