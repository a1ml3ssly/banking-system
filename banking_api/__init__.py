"""
banking_api/__init__.py — Flask application factory.
Usage:
    from banking_api import create_app
    app = create_app()
"""
from flask import Flask, send_from_directory
from flask_restx import Api
from . import config
import os

authorizations = {
    'Bearer': {
        'type':        'apiKey',
        'in':          'header',
        'name':        'Authorization',
        'description': 'Paste your JWT as: Bearer <token>',
    }
}

def create_app() -> Flask:
    app = Flask(__name__)
    api = Api(
        app,
        version=config.API_VERSION,
        title='Banking System API',
        description=(
            f'REST API for the banking system — `{config.SERVICE_DOMAIN}` service.\n\n'
            '**Auth flow:** POST `/token` with your `api_key` + `api_secret` '
            '→ copy the returned `access_token` → click **Authorize** above and paste '
            '`Bearer <token>`.'
        ),
        doc='/docs',
        prefix=f'/{config.SERVICE_DOMAIN}/api/{config.API_VERSION}',
        authorizations=authorizations,
        security='Bearer',
    )
    from .auth                     import ns as auth_ns
    from .routes.branches          import ns as branches_ns
    from .routes.clients           import ns as clients_ns
    from .routes.accounts          import ns as accounts_ns
    from .routes.transactions      import ns as transactions_ns
    from .routes.loans             import ns as loans_ns
    from .routes.loan_applications import ns as loan_apps_ns
    from .routes.cards             import ns as cards_ns
    from .routes.exchange_rates    import ns as exchange_rates_ns
    api.add_namespace(auth_ns,           path='/auth')
    api.add_namespace(branches_ns,       path='/branches')
    api.add_namespace(clients_ns,        path='/clients')
    api.add_namespace(accounts_ns,       path='/accounts')
    api.add_namespace(transactions_ns,   path='/transactions')
    api.add_namespace(loans_ns,          path='/loans')
    api.add_namespace(loan_apps_ns,      path='/loan-applications')
    api.add_namespace(cards_ns,          path='/cards')
    api.add_namespace(exchange_rates_ns, path='/exchange-rates')

    @app.route('/review')
    def review():
        return send_from_directory(
            os.path.dirname(__file__),
            'review.html'
        )

    return app
