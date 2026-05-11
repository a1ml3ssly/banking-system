import os

from dotenv import load_dotenv
from flask import Flask, Response
from flask_restx import Api

load_dotenv()

app = Flask(__name__)

api = Api(
    app,
    version='1.0',
    title='Banking System API',
    description='REST API for the Banking System database.',
    doc='/docs',
    prefix='/api',
)

# ─── Namespaces ───────────────────────────────────────────────────────────────
from routes.branches import ns as ns_branches
from routes.clients import ns as ns_clients
from routes.accounts import ns as ns_accounts
from routes.transactions import ns as ns_transactions
from routes.loans import ns as ns_loans
from routes.loan_applications import ns as ns_applications
from routes.cards import ns as ns_cards
from routes.exchange_rates import ns as ns_rates

api.add_namespace(ns_branches)
api.add_namespace(ns_clients)
api.add_namespace(ns_accounts)
api.add_namespace(ns_transactions)
api.add_namespace(ns_loans)
api.add_namespace(ns_applications)
api.add_namespace(ns_cards)
api.add_namespace(ns_rates)

# ─── Blueprints ───────────────────────────────────────────────────────────────
from auth import auth_bp
app.register_blueprint(auth_bp)

# ─── Utility routes ───────────────────────────────────────────────────────────
from db import query


@app.route('/health')
def health():
    try:
        query('SELECT 1 AS ok', fetchone=True)
        return {'status': 'ok', 'database': 'connected'}, 200
    except Exception as e:
        return {'status': 'error', 'detail': str(e)}, 500


@app.route('/review')
def review():
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'review.html')
    with open(html_path, 'r') as f:
        html = f.read()
    return Response(html, mimetype='text/html')


# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == '__main__':
    port = int(os.getenv('API_PORT', 5000))
    print(f'\n  Banking API running at  http://0.0.0.0:{port}')
    print(f'  Swagger UI available at http://0.0.0.0:{port}/docs\n')
    app.run(host='0.0.0.0', port=port, debug=True)
