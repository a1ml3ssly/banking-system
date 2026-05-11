from flask_restx import Namespace, Resource

from db import query
from utils import serialize_row, serialize_rows

ns = Namespace('loans', description='Loan management')


@ns.route('/')
class LoanList(Resource):
    def get(self):
        """Get all loans"""
        rows = query('''
            SELECT l.*, c.FirstName, c.LastName, lt.TypeName AS LoanTypeName
            FROM Loans l
            JOIN Clients c ON l.ClientID = c.ClientID
            JOIN LoanTypes lt ON l.LoanTypeID = lt.LoanTypeID
            ORDER BY l.LoanID
        ''')
        return serialize_rows(rows), 200


@ns.route('/<int:loan_id>')
@ns.param('loan_id', 'The loan identifier')
class Loan(Resource):
    def get(self, loan_id):
        """Get a single loan with payment history"""
        loan = query('''
            SELECT l.*, c.FirstName, c.LastName, lt.TypeName AS LoanTypeName
            FROM Loans l
            JOIN Clients c ON l.ClientID = c.ClientID
            JOIN LoanTypes lt ON l.LoanTypeID = lt.LoanTypeID
            WHERE l.LoanID = %s
        ''', (loan_id,), fetchone=True)
        if not loan:
            ns.abort(404, f'Loan {loan_id} not found')
        payments = query('SELECT * FROM LoanPayments WHERE LoanID = %s ORDER BY PaymentDate', (loan_id,))
        return {'loan': serialize_row(loan), 'payments': serialize_rows(payments)}, 200


@ns.route('/types')
class LoanTypeList(Resource):
    def get(self):
        """Get all loan types"""
        rows = query('SELECT * FROM LoanTypes ORDER BY LoanTypeID')
        return serialize_rows(rows), 200
