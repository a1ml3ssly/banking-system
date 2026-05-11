from flask_restx import Namespace, Resource, fields

from db import execute, query
from utils import serialize_row, serialize_rows

ns = Namespace('loan-applications', description='Loan applications & eligibility')

loan_application_model = ns.model('LoanApplication', {
    'ClientID':        fields.Integer(required=True, example=1),
    'LoanTypeID':      fields.Integer(required=True, example=1),
    'EmployeeID':      fields.Integer(example=2),
    'RequestedAmount': fields.Float(required=True,   example=50000.00),
    'RequestedTerm':   fields.Integer(required=True, example=36),
    'Purpose':         fields.String(example='Home renovation'),
})

eligibility_model = ns.model('EligibilityCheck', {
    'ClientID':        fields.Integer(required=True, example=1),
    'LoanTypeID':      fields.Integer(required=True, example=1),
    'RequestedAmount': fields.Float(required=True,   example=50000.00),
})

decision_model = ns.model('ApplicationDecision', {
    'Status':         fields.String(required=True, enum=['Approved', 'Rejected'], example='Approved'),
    'DecisionReason': fields.String(example='Meets all eligibility criteria'),
    'EmployeeID':     fields.Integer(example=2),
})


@ns.route('/')
class LoanApplicationList(Resource):
    def get(self):
        """Get all loan applications"""
        rows = query('''
            SELECT la.*, c.FirstName, c.LastName, lt.TypeName AS LoanTypeName
            FROM LoanApplications la
            JOIN Clients c ON la.ClientID = c.ClientID
            JOIN LoanTypes lt ON la.LoanTypeID = lt.LoanTypeID
            ORDER BY la.AppliedAt DESC
        ''')
        return serialize_rows(rows), 200

    @ns.expect(loan_application_model, validate=True)
    def post(self):
        """Submit a new loan application"""
        data   = ns.payload
        new_id = execute('''
            INSERT INTO LoanApplications
                (ClientID, LoanTypeID, EmployeeID, RequestedAmount, RequestedTerm, Purpose, Status)
            VALUES (%s, %s, %s, %s, %s, %s, 'Pending')
        ''', (
            data['ClientID'], data['LoanTypeID'], data.get('EmployeeID'),
            data['RequestedAmount'], data['RequestedTerm'], data.get('Purpose'),
        ))
        row = query('SELECT * FROM LoanApplications WHERE ApplicationID = %s', (new_id,), fetchone=True)
        return serialize_row(row), 201


@ns.route('/<int:app_id>/decision')
@ns.param('app_id', 'The application identifier')
class ApplicationDecision(Resource):
    @ns.expect(decision_model, validate=True)
    def put(self, app_id):
        """Approve or reject a loan application"""
        data = ns.payload
        app  = query('SELECT * FROM LoanApplications WHERE ApplicationID = %s', (app_id,), fetchone=True)
        if not app:
            ns.abort(404, f'Application {app_id} not found')
        if app['Status'] != 'Pending':
            ns.abort(400, f'Application already has status: {app["Status"]}')
        execute('''
            UPDATE LoanApplications
            SET Status = %s, DecisionReason = %s, DecidedAt = GETDATE()
            WHERE ApplicationID = %s
        ''', (data['Status'], data.get('DecisionReason'), app_id))
        row = query('SELECT * FROM LoanApplications WHERE ApplicationID = %s', (app_id,), fetchone=True)
        return serialize_row(row), 200


@ns.route('/eligibility/check')
class EligibilityCheck(Resource):
    @ns.expect(eligibility_model, validate=True)
    def post(self):
        """Check if a client is eligible for a loan"""
        data    = ns.payload
        profile = query('SELECT * FROM ClientFinancialProfiles WHERE ClientID = %s', (data['ClientID'],), fetchone=True)
        if not profile:
            ns.abort(404, 'No financial profile found for this client')
        rule = query('SELECT * FROM LoanEligibilityRules WHERE LoanTypeID = %s AND IsActive = 1', (data['LoanTypeID'],), fetchone=True)
        if not rule:
            ns.abort(404, 'No eligibility rules found for this loan type')

        failures      = []
        annual_income = float(profile['AnnualIncome'])
        existing_debt = float(profile['ExistingDebt'])
        requested     = float(data['RequestedAmount'])
        credit_score  = profile['CreditScore']

        if credit_score < rule['MinCreditScore']:
            failures.append(f'Credit score {credit_score} is below minimum {rule["MinCreditScore"]}')
        if annual_income < float(rule['MinAnnualIncome']):
            failures.append(f'Annual income {annual_income:,.0f} is below minimum {float(rule["MinAnnualIncome"]):,.0f}')

        total_debt = existing_debt + requested
        dti = (total_debt / annual_income) * 100 if annual_income > 0 else 999
        if dti > float(rule['MaxDebtToIncome']):
            failures.append(f'Debt-to-income ratio {dti:.1f}% exceeds maximum {float(rule["MaxDebtToIncome"])}%')
        if profile['EmploymentStatus'] == 'Unemployed':
            failures.append('Client must be employed or self-employed')

        eligible = len(failures) == 0
        return {
            'eligible':           eligible,
            'decision':           'Approved' if eligible else 'Rejected',
            'client_id':          data['ClientID'],
            'loan_type_id':       data['LoanTypeID'],
            'requested_amount':   requested,
            'credit_score':       credit_score,
            'annual_income':      annual_income,
            'debt_to_income_pct': round(dti, 2),
            'failure_reasons':    failures,
        }, 200
