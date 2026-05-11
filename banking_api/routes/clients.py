from flask_restx import Namespace, Resource, fields

from db import execute, query
from utils import serialize_row, serialize_rows

ns = Namespace('clients', description='Client management')

client_model = ns.model('NewClient', {
    'FirstName':   fields.String(required=True,  example='Yonatan'),
    'LastName':    fields.String(required=True,  example='Ben-David'),
    'Email':       fields.String(required=True,  example='yonatan@example.com'),
    'Phone':       fields.String(example='+972-52-9999999'),
    'DateOfBirth': fields.String(required=True,  example='1990-05-20'),
    'NationalID':  fields.String(required=True,  example='987654321'),
    'Address':     fields.String(example='14 Herzl St, Tel Aviv'),
    'BranchID':    fields.Integer(required=True, example=1),
})


@ns.route('/')
class ClientList(Resource):
    def get(self):
        """Get all clients"""
        rows = query('''
            SELECT c.*, b.BranchName
            FROM Clients c
            JOIN Branches b ON c.BranchID = b.BranchID
            ORDER BY c.ClientID
        ''')
        return serialize_rows(rows), 200

    @ns.expect(client_model, validate=True)
    def post(self):
        """Create a new client"""
        data = ns.payload
        new_id = execute('''
            INSERT INTO Clients
                (BranchID, FirstName, LastName, Email, Phone, DateOfBirth, NationalID, Address)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            data['BranchID'], data['FirstName'], data['LastName'],
            data['Email'], data.get('Phone'), data['DateOfBirth'],
            data['NationalID'], data.get('Address'),
        ))
        row = query('SELECT * FROM Clients WHERE ClientID = %s', (new_id,), fetchone=True)
        return serialize_row(row), 201


@ns.route('/<int:client_id>')
@ns.param('client_id', 'The client identifier')
class Client(Resource):
    def get(self, client_id):
        """Get a single client by ID"""
        row = query('''
            SELECT c.*, b.BranchName
            FROM Clients c
            JOIN Branches b ON c.BranchID = b.BranchID
            WHERE c.ClientID = %s
        ''', (client_id,), fetchone=True)
        if not row:
            ns.abort(404, f'Client {client_id} not found')
        return serialize_row(row), 200


@ns.route('/<int:client_id>/summary')
@ns.param('client_id', 'The client identifier')
class ClientSummary(Resource):
    def get(self, client_id):
        """Get full client summary"""
        client = query('SELECT * FROM Clients WHERE ClientID = %s', (client_id,), fetchone=True)
        if not client:
            ns.abort(404, f'Client {client_id} not found')
        accounts = query('SELECT * FROM Accounts WHERE ClientID = %s', (client_id,))
        loans    = query('SELECT * FROM Loans WHERE ClientID = %s', (client_id,))
        cards    = query('SELECT * FROM CreditCards WHERE ClientID = %s', (client_id,))
        profile  = query('SELECT * FROM ClientFinancialProfiles WHERE ClientID = %s', (client_id,), fetchone=True)
        return {
            'client':            serialize_row(client),
            'accounts':          serialize_rows(accounts),
            'loans':             serialize_rows(loans),
            'credit_cards':      serialize_rows(cards),
            'financial_profile': serialize_row(profile),
        }, 200


@ns.route('/<int:client_id>/accounts')
@ns.param('client_id', 'The client identifier')
class ClientAccounts(Resource):
    def get(self, client_id):
        """Get all accounts for a client"""
        rows = query('''
            SELECT a.*, at.TypeName, at.InterestRate
            FROM Accounts a
            JOIN AccountTypes at ON a.AccountTypeID = at.AccountTypeID
            WHERE a.ClientID = %s
        ''', (client_id,))
        return serialize_rows(rows), 200
