"""
routes/loan_applications.py

GET  /api/v1/loan-applications              — list applications
POST /api/v1/loan-applications              — submit a new application  [admin]
GET  /api/v1/loan-applications/{id}         — get a single application
POST /api/v1/loan-applications/{id}/decision — approve or reject  [admin]
GET  /api/v1/loan-applications/{id}/eligibility — run eligibility check against rules
"""

import datetime
from flask_restx import Namespace, Resource, fields, abort, reqparse

from .. import db
from ..auth import require_auth
from ..utils import serialize_rows, serialize_row, paginate

ns = Namespace('loan-applications', description='Loan application lifecycle')

# ── Swagger models ─────────────────────────────────────────────────────────────
application_model = ns.model('LoanApplication', {
    'ApplicationID':       fields.Integer(readonly=True),
    'ClientID':            fields.Integer,
    'LoanType':            fields.String,
    'RequestedAmount':     fields.Float,
    'RequestedTermMonths': fields.Integer,
    'Purpose':             fields.String,
    'Status':              fields.String(description='pending | approved | rejected | cancelled'),
    'EligibilityScore':    fields.Float,
    'ReviewedBy':          fields.Integer,
    'ReviewedAt':          fields.String,
    'RejectionReason':     fields.String,
    'ApprovedAmount':      fields.Float,
    'ApprovedRate':        fields.Float,
    'ResultantLoanID':     fields.Integer,
    'SubmittedAt':         fields.String,
})

application_input = ns.model('LoanApplicationInput', {
    'ClientID':        fields.Integer(required=True),
    'LoanType':        fields.String(required=True,  description='personal | mortgage | auto | business'),
    'RequestedAmount': fields.Float(required=True,   description='Amount requested'),
    'TermMonths':      fields.Integer(required=True, description='Repayment term in months (stored as RequestedTermMonths)'),
    'Purpose':         fields.String(required=False, description='Reason for the loan'),
})

decision_input = ns.model('DecisionInput', {
    'decision':       fields.String(required=True,  description='approved | rejected'),
    'decision_note':  fields.String(required=False, description='Officer note / rejection reason'),
    'ApprovedAmount': fields.Float(required=False,  description='Approved loan amount (for approvals)'),
    'ApprovedRate':   fields.Float(required=False,  description='Approved interest rate % (for approvals)'),
})

eligibility_result = ns.model('EligibilityResult', {
    'eligible':       fields.Boolean,
    'score':          fields.Integer(description='0–100 composite score'),
    'reasons':        fields.List(fields.String, description='List of pass/fail reasons'),
    'credit_score':   fields.Float,
    'dti_ratio':      fields.Float,
    'monthly_income': fields.Float,
})

page_parser = reqparse.RequestParser()
page_parser.add_argument('page',   type=int, default=1,  location='args')
page_parser.add_argument('per_page', type=int, default=20, location='args')
page_parser.add_argument('status', type=str, default='', location='args')


# ── Resources ─────────────────────────────────────────────────────────────────
@ns.route('/')
class LoanApplicationList(Resource):

    @require_auth()
    @ns.expect(page_parser)
    @ns.response(503, 'Database unavailable')
    def get(self):
        """List loan applications, newest first."""
        args     = page_parser.parse_args()
        page     = max(1, args['page'])
        per_page = min(100, max(1, args['per_page']))
        status   = args['status'].strip()

        try:
            if status:
                rows = db.query(
                    'SELECT * FROM LoanApplications WHERE Status = %s ORDER BY SubmittedAt DESC',
                    (status,),
                )
            else:
                rows = db.query('SELECT * FROM LoanApplications ORDER BY SubmittedAt DESC')
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))

        return paginate(serialize_rows(rows), page, per_page)

    @require_auth(roles=['admin'])
    @ns.expect(application_input, validate=True)
    @ns.marshal_with(application_model, code=201)
    @ns.response(400, 'Validation error')
    @ns.response(503, 'Database unavailable')
    def post(self):
        """Submit a new loan application. [admin only]"""
        p = ns.payload
        try:
            if not db.query_one('SELECT ClientID FROM Clients WHERE ClientID = %s', (p['ClientID'],)):
                abort(400, message=f"Client {p['ClientID']} does not exist.")

            row = db.execute_returning(
                """
                INSERT INTO LoanApplications
                    (ClientID, LoanType, RequestedAmount, RequestedTermMonths, Purpose, Status)
                OUTPUT INSERTED.*
                VALUES (%s, %s, %s, %s, %s, 'pending')
                """,
                (
                    p['ClientID'],
                    p['LoanType'],
                    p['RequestedAmount'],
                    p['TermMonths'],
                    p.get('Purpose', ''),
                ),
            )
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))
        return serialize_row(row), 201


@ns.route('/<int:application_id>')
@ns.param('application_id', 'Application ID')
class LoanApplicationDetail(Resource):

    @require_auth()
    @ns.marshal_with(application_model)
    @ns.response(404, 'Application not found')
    @ns.response(503, 'Database unavailable')
    def get(self, application_id):
        """Get a single loan application by ID."""
        try:
            row = db.query_one(
                'SELECT * FROM LoanApplications WHERE ApplicationID = %s', (application_id,)
            )
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))
        if not row:
            abort(404, message=f'Application {application_id} not found.')
        return serialize_row(row)


@ns.route('/<int:application_id>/decision')
@ns.param('application_id', 'Application ID')
class LoanApplicationDecision(Resource):

    @require_auth(roles=['admin'])
    @ns.expect(decision_input, validate=True)
    @ns.marshal_with(application_model)
    @ns.response(400, 'Invalid decision or application already decided')
    @ns.response(404, 'Application not found')
    @ns.response(503, 'Database unavailable')
    def post(self, application_id):
        """Record an approval or rejection decision. [admin only]"""
        p        = ns.payload
        decision = p['decision'].lower()
        if decision not in ('approved', 'rejected'):
            abort(400, message="Decision must be 'approved' or 'rejected'.")

        try:
            app = db.query_one(
                'SELECT * FROM LoanApplications WHERE ApplicationID = %s', (application_id,)
            )
            if not app:
                abort(404, message=f'Application {application_id} not found.')
            if app['Status'] != 'pending':
                abort(400, message=f"Application is already '{app['Status']}' — cannot decide again.")

            row = db.execute_returning(
                """
                UPDATE LoanApplications
                SET    Status          = %s,
                       ReviewedAt      = GETDATE(),
                       RejectionReason = %s,
                       ApprovedAmount  = %s,
                       ApprovedRate    = %s
                OUTPUT INSERTED.*
                WHERE  ApplicationID = %s
                """,
                (
                    decision,
                    p.get('decision_note', ''),
                    p.get('ApprovedAmount'),
                    p.get('ApprovedRate'),
                    application_id,
                ),
            )
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))
        return serialize_row(row)


@ns.route('/<int:application_id>/eligibility')
@ns.param('application_id', 'Application ID')
class LoanEligibilityCheck(Resource):

    @require_auth()
    @ns.marshal_with(eligibility_result)
    @ns.response(404, 'Application or financial profile not found')
    @ns.response(503, 'Database unavailable')
    def get(self, application_id):
        """
        Run the eligibility engine against the active LoanEligibilityRules.
        Requires a ClientFinancialProfile to exist for the applicant.
        """
        try:
            app = db.query_one(
                'SELECT * FROM LoanApplications WHERE ApplicationID = %s', (application_id,)
            )
            if not app:
                abort(404, message=f'Application {application_id} not found.')

            profile = db.query_one(
                'SELECT * FROM ClientFinancialProfiles WHERE ClientID = %s',
                (app['ClientID'],),
            )
            if not profile:
                abort(404, message=f"No financial profile found for client {app['ClientID']}.")

            rules = db.query('SELECT * FROM LoanEligibilityRules WHERE IsActive = 1')
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))

        # ── Eligibility engine ─────────────────────────────────────────────────
        reasons    = []
        score      = 100
        eligible   = True

        credit_score     = float(profile.get('CreditScore', 0) or 0)
        monthly_income   = float(profile.get('MonthlyIncome', 0) or 0)
        monthly_expenses = float(profile.get('MonthlyExpenses', 0) or 0)
        dti_ratio        = (monthly_expenses / monthly_income) if monthly_income > 0 else 999.0
        years_employed   = float(profile.get('YearsEmployed', 0) or 0)
        bankruptcy       = bool(profile.get('BankruptcyHistory', False))
        requested        = float(app['RequestedAmount'])
        app_loan_type    = (app.get('LoanType') or '').lower()

        for rule in rules:
            rule_name = rule.get('RuleName', '')
            loan_type = rule.get('LoanType')
            if loan_type and loan_type.lower() != app_loan_type:
                continue

            min_credit = rule.get('MinCreditScore')
            if min_credit is not None:
                if credit_score < float(min_credit):
                    reasons.append(f'FAIL [{rule_name}]: credit score {credit_score} < minimum {min_credit}')
                    score   -= 20
                    eligible = False
                else:
                    reasons.append(f'PASS [{rule_name}]: credit score {credit_score} >= {min_credit}')

            max_dti = rule.get('MaxDTIRatio')
            if max_dti is not None:
                if dti_ratio > float(max_dti):
                    reasons.append(f'FAIL [{rule_name}]: DTI {dti_ratio:.2f} > maximum {max_dti}')
                    score   -= 15
                    eligible = False
                else:
                    reasons.append(f'PASS [{rule_name}]: DTI {dti_ratio:.2f} <= {max_dti}')

            min_income = rule.get('MinMonthlyIncome')
            if min_income is not None:
                if monthly_income < float(min_income):
                    reasons.append(f'FAIL [{rule_name}]: income {monthly_income} < minimum {min_income}')
                    score   -= 15
                    eligible = False
                else:
                    reasons.append(f'PASS [{rule_name}]: income {monthly_income} >= {min_income}')

            min_years = rule.get('MinYearsEmployed')
            if min_years is not None:
                if years_employed < float(min_years):
                    reasons.append(f'FAIL [{rule_name}]: years employed {years_employed} < minimum {min_years}')
                    score   -= 10
                    eligible = False
                else:
                    reasons.append(f'PASS [{rule_name}]: years employed {years_employed} >= {min_years}')

            max_loan = rule.get('MaxLoanAmount')
            if max_loan is not None:
                if requested > float(max_loan):
                    reasons.append(f'FAIL [{rule_name}]: requested {requested} > maximum {max_loan}')
                    score   -= 20
                    eligible = False
                else:
                    reasons.append(f'PASS [{rule_name}]: requested {requested} <= {max_loan}')

            allow_bankruptcy = rule.get('AllowBankruptcy', True)
            if not allow_bankruptcy and bankruptcy:
                reasons.append(f'FAIL [{rule_name}]: bankruptcy history disqualifies applicant')
                score   -= 30
                eligible = False

        score = max(0, score)

        return {
            'eligible':       eligible,
            'score':          score,
            'reasons':        reasons,
            'credit_score':   credit_score,
            'dti_ratio':      round(dti_ratio, 4),
            'monthly_income': monthly_income,
        }
