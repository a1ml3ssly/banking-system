"""
routes/exchange_rates.py

GET  /api/v1/exchange-rates                      — list all rates
GET  /api/v1/exchange-rates/{base}/{target}       — get a specific pair
"""

from flask_restx import Namespace, Resource, fields, abort

from .. import db
from ..auth import require_auth
from ..utils import serialize_rows, serialize_row

ns = Namespace('exchange-rates', description='Currency exchange rate lookups')

# ── Swagger models ─────────────────────────────────────────────────────────────
rate_model = ns.model('ExchangeRate', {
    'RateID':        fields.Integer(readonly=True),
    'FromCurrency':  fields.String,
    'ToCurrency':    fields.String,
    'Rate':          fields.Float,
    'EffectiveDate': fields.String,
    'CreatedAt':     fields.String,
})


# ── Resources ─────────────────────────────────────────────────────────────────
@ns.route('/')
class ExchangeRateList(Resource):

    @require_auth()
    @ns.marshal_list_with(rate_model)
    @ns.response(503, 'Database unavailable')
    def get(self):
        """List all exchange rates, sorted by base currency."""
        try:
            rows = db.query('SELECT * FROM CurrencyRates ORDER BY FromCurrency, ToCurrency')
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))
        return serialize_rows(rows)


@ns.route('/<string:base>/<string:target>')
@ns.param('base',   'Base currency code (e.g. USD)')
@ns.param('target', 'Target currency code (e.g. ILS)')
class ExchangeRatePair(Resource):

    @require_auth()
    @ns.marshal_with(rate_model)
    @ns.response(404, 'Rate not found for this pair')
    @ns.response(503, 'Database unavailable')
    def get(self, base: str, target: str):
        """Get the exchange rate for a specific currency pair."""
        try:
            row = db.query_one(
                """
                SELECT * FROM CurrencyRates
                WHERE FromCurrency = %s
                  AND ToCurrency   = %s
                ORDER BY EffectiveDate DESC
                """,
                (base.upper(), target.upper()),
            )
        except db.DatabaseUnavailableError as exc:
            abort(503, message=str(exc))
        if not row:
            abort(404, message=f'No exchange rate found for {base.upper()} → {target.upper()}.')
        return serialize_row(row)
