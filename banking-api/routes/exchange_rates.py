from flask_restx import Namespace, Resource

from db import query
from utils import serialize_row, serialize_rows

ns = Namespace('exchange-rates', description='Currency exchange rates')


@ns.route('/')
class ExchangeRateList(Resource):
    def get(self):
        """Get all exchange rates"""
        rows = query('SELECT * FROM ExchangeRates ORDER BY BaseCurrency, TargetCurrency')
        return serialize_rows(rows), 200


@ns.route('/<string:base>/<string:target>')
@ns.param('base',   'Base currency (e.g. ILS)')
@ns.param('target', 'Target currency (e.g. USD)')
class ExchangeRate(Resource):
    def get(self, base, target):
        """Get exchange rate between two currencies"""
        row = query(
            'SELECT * FROM ExchangeRates WHERE BaseCurrency = %s AND TargetCurrency = %s',
            (base.upper(), target.upper()), fetchone=True,
        )
        if not row:
            ns.abort(404, f'No rate found for {base.upper()} to {target.upper()}')
        return serialize_row(row), 200
