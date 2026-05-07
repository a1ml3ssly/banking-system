from flask import Flask, request, jsonify
from flask_restx import Api, Resource, fields, Namespace
from db import query, execute
import os
import jwt
import time
from dotenv import load_dotenv
from datetime import date, datetime
from werkzeug.security import check_password_hash

load_dotenv()

# ─────────────────────────────────────────────
#  JWT config
# ─────────────────────────────────────────────
JWT_SECRET         = os.getenv("JWT_SECRET", "BankingDemoSecret2024!")
JWT_ALGORITHM      = "HS256"
JWT_EXPIRY_SECONDS = int(os.getenv("JWT_EXPIRY_SECONDS", 3600))

ROLE_TO_POLICY = {
    "admin":    "admin-policy",
    "readonly": "readonly-policy",
}

# ─────────────────────────────────────────────
#  App & API setup
# ─────────────────────────────────────────────
app = Flask(__name__)

api = Api(
    app,
    version='1.0',
    title='Banking System API',
    description='REST API for the Banking System database.',
    doc='/docs',
    prefix='/api'
)

def serialize(obj):
    if isinstance(obj, (date, datetime)):
        return obj.isoformat()
    return obj

def serialize_row(row):
    if row is None:
        return None
    return {k: serialize(v) for k, v in row.items()}

def serialize_rows(rows):
    return [serialize_row(r) for r in rows]

# ─────────────────────────────────────────────
#  Namespaces
# ─────────────────────────────────────────────
ns_branches     = Namespace('branches',          description='Bank branches')
ns_clients      = Namespace('clients',           description='Client management')
ns_accounts     = Namespace('accounts',          description='Bank accounts')
ns_transactions = Namespace('transactions',      description='Deposits, withdrawals & transfers')
ns_loans        = Namespace('loans',             description='Loan management')
ns_applications = Namespace('loan-applications', description='Loan applications & eligibility')
ns_cards        = Namespace('credit-cards',      description='Credit card operations')
ns_rates        = Namespace('exchange-rates',    description='Currency exchange rates')

api.add_namespace(ns_branches)
api.add_namespace(ns_clients)
api.add_namespace(ns_accounts)
api.add_namespace(ns_transactions)
api.add_namespace(ns_loans)
api.add_namespace(ns_applications)
api.add_namespace(ns_cards)
api.add_namespace(ns_rates)

# ─────────────────────────────────────────────
#  Swagger models
# ─────────────────────────────────────────────
client_model = ns_clients.model('NewClient', {
    'FirstName':   fields.String(required=True,  example='Yonatan'),
    'LastName':    fields.String(required=True,  example='Ben-David'),
    'Email':       fields.String(required=True,  example='yonatan@example.com'),
    'Phone':       fields.String(example='+972-52-9999999'),
    'DateOfBirth': fields.String(required=True,  example='1990-05-20'),
    'NationalID':  fields.String(required=True,  example='987654321'),
    'Address':     fields.String(example='14 Herzl St, Tel Aviv'),
    'BranchID':    fields.Integer(required=True, example=1),
})

account_model = ns_accounts.model('NewAccount', {
    'ClientID':      fields.Integer(required=True, example=1),
    'AccountTypeID': fields.Integer(required=True, example=1),
    'BranchID':      fields.Integer(required=True, example=1),
    'AccountNumber': fields.String(required=True,  example='ACC-010-001'),
    'Balance':       fields.Float(example=0.0),
    'Currency':      fields.String(example='ILS'),
})

deposit_model = ns_transactions.model('DepositWithdrawal', {
    'AccountID':   fields.Integer(required=True, example=1),
    'Amount':      fields.Float(required=True,   example=1000.00),
    'Description': fields.String(example='Cash deposit'),
    'Type':        fields.String(required=True,  enum=['Deposit', 'Withdrawal'], example='Deposit'),
})

transfer_model = ns_transactions.model('Transfer', {
    'FromAccountID': fields.Integer(required=True, example=1),
    'ToAccountID':   fields.Integer(required=True, example=3),
    'Amount':        fields.Float(required=True,   example=500.00),
    'Description':   fields.String(example='Rent payment'),
})

loan_application_model = ns_applications.model('LoanApplication', {
    'ClientID':        fields.Integer(required=True, example=1),
    'LoanTypeID':      fields.Integer(required=True, example=1),
    'EmployeeID':      fields.Integer(example=2),
    'RequestedAmount': fields.Float(required=True,   example=50000.00),
    'RequestedTerm':   fields.Integer(required=True, example=36),
    'Purpose':         fields.String(example='Home renovation'),
})

eligibility_model = ns_applications.model('EligibilityCheck', {
    'ClientID':        fields.Integer(required=True, example=1),
    'LoanTypeID':      fields.Integer(required=True, example=1),
    'RequestedAmount': fields.Float(required=True,   example=50000.00),
})

decision_model = ns_applications.model('ApplicationDecision', {
    'Status':         fields.String(required=True, enum=['Approved', 'Rejected'], example='Approved'),
    'DecisionReason': fields.String(example='Meets all eligibility criteria'),
    'EmployeeID':     fields.Integer(example=2),
})

# ═══════════════════════════════════════════════════
#  BRANCHES
# ═══════════════════════════════════════════════════
@ns_branches.route('/')
class BranchList(Resource):
    def get(self):
        """Get all branches"""
        rows = query('SELECT * FROM Branches ORDER BY BranchID')
        return serialize_rows(rows), 200

@ns_branches.route('/<int:branch_id>')
@ns_branches.param('branch_id', 'The branch identifier')
class Branch(Resource):
    def get(self, branch_id):
        """Get a single branch by ID"""
        row = query('SELECT * FROM Branches WHERE BranchID = %s', (branch_id,), fetchone=True)
        if not row:
            api.abort(404, f'Branch {branch_id} not found')
        return serialize_row(row), 200

# ═══════════════════════════════════════════════════
#  CLIENTS
# ═══════════════════════════════════════════════════
@ns_clients.route('/')
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

    @ns_clients.expect(client_model, validate=True)
    def post(self):
        """Create a new client"""
        data = api.payload
        new_id = execute('''
            INSERT INTO Clients
                (BranchID, FirstName, LastName, Email, Phone, DateOfBirth, NationalID, Address)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        ''', (
            data['BranchID'], data['FirstName'], data['LastName'],
            data['Email'], data.get('Phone'), data['DateOfBirth'],
            data['NationalID'], data.get('Address')
        ))
        row = query('SELECT * FROM Clients WHERE ClientID = %s', (new_id,), fetchone=True)
        return serialize_row(row), 201

@ns_clients.route('/<int:client_id>')
@ns_clients.param('client_id', 'The client identifier')
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
            api.abort(404, f'Client {client_id} not found')
        return serialize_row(row), 200

@ns_clients.route('/<int:client_id>/summary')
@ns_clients.param('client_id', 'The client identifier')
class ClientSummary(Resource):
    def get(self, client_id):
        """Get full client summary"""
        client = query('SELECT * FROM Clients WHERE ClientID = %s', (client_id,), fetchone=True)
        if not client:
            api.abort(404, f'Client {client_id} not found')
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

@ns_clients.route('/<int:client_id>/accounts')
@ns_clients.param('client_id', 'The client identifier')
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

# ═══════════════════════════════════════════════════
#  ACCOUNTS
# ═══════════════════════════════════════════════════
@ns_accounts.route('/')
class AccountList(Resource):
    def get(self):
        """Get all accounts"""
        rows = query('''
            SELECT a.*, c.FirstName, c.LastName, at.TypeName
            FROM Accounts a
            JOIN Clients c ON a.ClientID = c.ClientID
            JOIN AccountTypes at ON a.AccountTypeID = at.AccountTypeID
            ORDER BY a.AccountID
        ''')
        return serialize_rows(rows), 200

    @ns_accounts.expect(account_model, validate=True)
    def post(self):
        """Open a new bank account"""
        data = api.payload
        new_id = execute('''
            INSERT INTO Accounts (ClientID, AccountTypeID, BranchID, AccountNumber, Balance, Currency)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (
            data['ClientID'], data['AccountTypeID'], data['BranchID'],
            data['AccountNumber'], data.get('Balance', 0.00), data.get('Currency', 'ILS')
        ))
        row = query('SELECT * FROM Accounts WHERE AccountID = %s', (new_id,), fetchone=True)
        return serialize_row(row), 201

@ns_accounts.route('/<int:account_id>')
@ns_accounts.param('account_id', 'The account identifier')
class Account(Resource):
    def get(self, account_id):
        """Get a single account"""
        row = query('''
            SELECT a.*, c.FirstName, c.LastName, at.TypeName
            FROM Accounts a
            JOIN Clients c ON a.ClientID = c.ClientID
            JOIN AccountTypes at ON a.AccountTypeID = at.AccountTypeID
            WHERE a.AccountID = %s
        ''', (account_id,), fetchone=True)
        if not row:
            api.abort(404, f'Account {account_id} not found')
        return serialize_row(row), 200

@ns_accounts.route('/<int:account_id>/transactions')
@ns_accounts.param('account_id', 'The account identifier')
class AccountTransactions(Resource):
    def get(self, account_id):
        """Get all transactions for an account"""
        rows = query('''
            SELECT * FROM Transactions
            WHERE AccountID = %s OR RelatedAccountID = %s
            ORDER BY TransactionDate DESC
        ''', (account_id, account_id))
        return serialize_rows(rows), 200

# ═══════════════════════════════════════════════════
#  TRANSACTIONS
# ═══════════════════════════════════════════════════
@ns_transactions.route('/')
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

@ns_transactions.route('/deposit-withdrawal')
class DepositWithdrawal(Resource):
    @ns_transactions.expect(deposit_model, validate=True)
    def post(self):
        """Perform a deposit or withdrawal"""
        data = api.payload
        account = query('SELECT * FROM Accounts WHERE AccountID = %s', (data['AccountID'],), fetchone=True)
        if not account:
            api.abort(404, 'Account not found')
        amount  = float(data['Amount'])
        tx_type = data['Type']
        if tx_type == 'Withdrawal':
            if account['Balance'] < amount:
                api.abort(400, 'Insufficient funds')
            new_balance = account['Balance'] - amount
        else:
            new_balance = account['Balance'] + amount
        execute('UPDATE Accounts SET Balance = %s WHERE AccountID = %s', (new_balance, data['AccountID']))
        new_id = execute('''
            INSERT INTO Transactions (AccountID, TransactionType, Amount, Description, Status)
            VALUES (%s, %s, %s, %s, 'Completed')
        ''', (data['AccountID'], tx_type, amount, data.get('Description', '')))
        return {'message': f'{tx_type} successful', 'transaction_id': new_id, 'new_balance': new_balance}, 201

@ns_transactions.route('/transfer')
class Transfer(Resource):
    @ns_transactions.expect(transfer_model, validate=True)
    def post(self):
        """Transfer funds between two accounts"""
        data     = api.payload
        amount   = float(data['Amount'])
        from_acc = query('SELECT * FROM Accounts WHERE AccountID = %s', (data['FromAccountID'],), fetchone=True)
        to_acc   = query('SELECT * FROM Accounts WHERE AccountID = %s', (data['ToAccountID'],),   fetchone=True)
        if not from_acc:
            api.abort(404, 'Source account not found')
        if not to_acc:
            api.abort(404, 'Destination account not found')
        if from_acc['Balance'] < amount:
            api.abort(400, 'Insufficient funds')
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

# ═══════════════════════════════════════════════════
#  LOANS
# ═══════════════════════════════════════════════════
@ns_loans.route('/')
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

@ns_loans.route('/<int:loan_id>')
@ns_loans.param('loan_id', 'The loan identifier')
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
            api.abort(404, f'Loan {loan_id} not found')
        payments = query('SELECT * FROM LoanPayments WHERE LoanID = %s ORDER BY PaymentDate', (loan_id,))
        return {'loan': serialize_row(loan), 'payments': serialize_rows(payments)}, 200

@ns_loans.route('/types')
class LoanTypeList(Resource):
    def get(self):
        """Get all loan types"""
        rows = query('SELECT * FROM LoanTypes ORDER BY LoanTypeID')
        return serialize_rows(rows), 200

# ═══════════════════════════════════════════════════
#  LOAN APPLICATIONS & ELIGIBILITY
# ═══════════════════════════════════════════════════
@ns_applications.route('/')
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

    @ns_applications.expect(loan_application_model, validate=True)
    def post(self):
        """Submit a new loan application"""
        data   = api.payload
        new_id = execute('''
            INSERT INTO LoanApplications
                (ClientID, LoanTypeID, EmployeeID, RequestedAmount, RequestedTerm, Purpose, Status)
            VALUES (%s, %s, %s, %s, %s, %s, 'Pending')
        ''', (data['ClientID'], data['LoanTypeID'], data.get('EmployeeID'),
              data['RequestedAmount'], data['RequestedTerm'], data.get('Purpose')))
        row = query('SELECT * FROM LoanApplications WHERE ApplicationID = %s', (new_id,), fetchone=True)
        return serialize_row(row), 201

@ns_applications.route('/<int:app_id>/decision')
@ns_applications.param('app_id', 'The application identifier')
class ApplicationDecision(Resource):
    @ns_applications.expect(decision_model, validate=True)
    def put(self, app_id):
        """Approve or reject a loan application"""
        data = api.payload
        app  = query('SELECT * FROM LoanApplications WHERE ApplicationID = %s', (app_id,), fetchone=True)
        if not app:
            api.abort(404, f'Application {app_id} not found')
        if app['Status'] != 'Pending':
            api.abort(400, f'Application already has status: {app["Status"]}')
        execute('''
            UPDATE LoanApplications
            SET Status = %s, DecisionReason = %s, DecidedAt = GETDATE()
            WHERE ApplicationID = %s
        ''', (data['Status'], data.get('DecisionReason'), app_id))
        row = query('SELECT * FROM LoanApplications WHERE ApplicationID = %s', (app_id,), fetchone=True)
        return serialize_row(row), 200

@ns_applications.route('/eligibility/check')
class EligibilityCheck(Resource):
    @ns_applications.expect(eligibility_model, validate=True)
    def post(self):
        """Check if a client is eligible for a loan"""
        data    = api.payload
        profile = query('SELECT * FROM ClientFinancialProfiles WHERE ClientID = %s', (data['ClientID'],), fetchone=True)
        if not profile:
            api.abort(404, 'No financial profile found for this client')
        rule = query('SELECT * FROM LoanEligibilityRules WHERE LoanTypeID = %s AND IsActive = 1', (data['LoanTypeID'],), fetchone=True)
        if not rule:
            api.abort(404, 'No eligibility rules found for this loan type')
        failures       = []
        annual_income  = float(profile['AnnualIncome'])
        existing_debt  = float(profile['ExistingDebt'])
        requested      = float(data['RequestedAmount'])
        credit_score   = profile['CreditScore']
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

# ═══════════════════════════════════════════════════
#  CREDIT CARDS
# ═══════════════════════════════════════════════════
@ns_cards.route('/')
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

@ns_cards.route('/<int:card_id>')
@ns_cards.param('card_id', 'The card identifier')
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
            api.abort(404, f'Card {card_id} not found')
        transactions = query('SELECT TOP 20 * FROM CreditCardTransactions WHERE CardID = %s ORDER BY TransactionDate DESC', (card_id,))
        billing      = query('SELECT TOP 3 * FROM BillingCycles WHERE CardID = %s ORDER BY CycleEndDate DESC', (card_id,))
        return {'card': serialize_row(card), 'transactions': serialize_rows(transactions), 'billing': serialize_rows(billing)}, 200

@ns_cards.route('/client/<int:client_id>')
@ns_cards.param('client_id', 'The client identifier')
class ClientCreditCards(Resource):
    def get(self, client_id):
        """Get all credit cards for a client"""
        rows = query('SELECT * FROM CreditCards WHERE ClientID = %s', (client_id,))
        return serialize_rows(rows), 200

# ═══════════════════════════════════════════════════
#  EXCHANGE RATES
# ═══════════════════════════════════════════════════
@ns_rates.route('/')
class ExchangeRateList(Resource):
    def get(self):
        """Get all exchange rates"""
        rows = query('SELECT * FROM ExchangeRates ORDER BY BaseCurrency, TargetCurrency')
        return serialize_rows(rows), 200

@ns_rates.route('/<string:base>/<string:target>')
@ns_rates.param('base',   'Base currency (e.g. ILS)')
@ns_rates.param('target', 'Target currency (e.g. USD)')
class ExchangeRate(Resource):
    def get(self, base, target):
        """Get exchange rate between two currencies"""
        row = query('SELECT * FROM ExchangeRates WHERE BaseCurrency = %s AND TargetCurrency = %s',
                    (base.upper(), target.upper()), fetchone=True)
        if not row:
            api.abort(404, f'No rate found for {base.upper()} to {target.upper()}')
        return serialize_row(row), 200

# ─────────────────────────────────────────────
#  /token
# ─────────────────────────────────────────────
@app.route('/token', methods=['POST'])
def get_token():
    """Exchange API key + secret for a short-lived JWT token."""
    data = request.get_json(silent=True)
    if not data or not data.get('key') or not data.get('secret'):
        return jsonify({'error': 'key and secret are required'}), 400
    credential = query(
        'SELECT * FROM ApiCredentials WHERE ApiKey = %s AND IsActive = 1',
        (data['key'],), fetchone=True,
    )
    if not credential:
        return jsonify({'error': 'Invalid key or secret'}), 401
    from werkzeug.security import check_password_hash
    if not check_password_hash(credential['ApiSecretHash'], data['secret']):
        return jsonify({'error': 'Invalid key or secret'}), 401
    now    = int(time.time())
    policy = ROLE_TO_POLICY.get(credential['Role'], 'readonly-policy')
    payload = {
        'sub':  credential['ApiKey'],
        'pol':  policy,
        'role': credential['Role'],
        'name': credential['Name'],
        'iat':  now,
        'exp':  now + JWT_EXPIRY_SECONDS,
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    execute('UPDATE ApiCredentials SET LastUsedAt = GETDATE() WHERE CredentialID = %s', (credential['CredentialID'],))
    return jsonify({'access_token': token, 'token_type': 'Bearer', 'expires_in': JWT_EXPIRY_SECONDS, 'role': credential['Role']}), 200

# ─────────────────────────────────────────────
#  Health check
# ─────────────────────────────────────────────
@app.route('/health')
def health():
    try:
        query('SELECT 1 AS ok', fetchone=True)
        return {'status': 'ok', 'database': 'connected'}, 200
    except Exception as e:
        return {'status': 'error', 'detail': str(e)}, 500

# ─────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────

# ─────────────────────────────────────────────
#  /review — Developer & QA documentation
# ─────────────────────────────────────────────
@app.route('/review')
def review():
    from flask import Response
    import os
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'review.html')
    with open(html_path, 'r') as f:
        html = f.read()
    return Response(html, mimetype='text/html')

# ─────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────


# ─────────────────────────────────────────────
#  Entry point
# ─────────────────────────────────────────────
if __name__ == '__main__':
    port = int(os.getenv('API_PORT', 5000))
    print(f'\n  Banking API running at  http://0.0.0.0:{port}')
    print(f'  Swagger UI available at http://0.0.0.0:{port}/docs\n')
    app.run(host='0.0.0.0', port=port, debug=True)
