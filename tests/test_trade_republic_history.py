from app.core.config import settings
from app.services import trade_republic
import asyncio
import pytest


class FakeTimelineApi:
    def __init__(self):
        self.after_values = []
        self.responses = {
            None: {
                "items": [
                    {"id": "newer", "timestamp": "2026-05-01T12:00:00+00:00", "eventType": "CARD_TRANSACTION"},
                ],
                "cursors": {"after": "cursor-2"},
            },
            "cursor-2": {
                "items": [
                    {"id": "wanted", "timestamp": "2026-04-16T12:00:00+00:00", "eventType": "CARD_TRANSACTION"},
                    {"id": "older", "timestamp": "2026-04-01T12:00:00+00:00", "eventType": "CARD_TRANSACTION"},
                ],
                "cursors": {},
            },
        }
        self.subscriptions = {}
        self.current_response = None

    async def timeline_transactions(self, after=None):
        self.after_values.append(after)
        subscription_id = f"sub-{len(self.after_values)}"
        self.subscriptions[subscription_id] = {"type": "timelineTransactions", "after": after}
        self.current_response = self.responses[after]
        return subscription_id

    async def recv(self):
        subscription_id = f"sub-{len(self.after_values)}"
        return subscription_id, self.subscriptions[subscription_id], self.current_response

    async def unsubscribe(self, subscription_id):
        self.subscriptions.pop(subscription_id, None)


class FakePortfolioApi:
    def __init__(self):
        self.subscriptions = {}
        self.responses = {}
        self.counter = 0

    async def compact_portfolio(self):
        return self._subscribe(
            {"type": "compactPortfolio"},
            {
                "positions": [
                    {"instrumentId": "IE00B57X3V84", "netSize": "31.293027", "averageBuyIn": "79.922"},
                    {"instrumentId": "XF000ETH0019", "netSize": "0.0076", "averageBuyIn": "3807.6711"},
                ]
            },
        )

    async def cash(self):
        return self._subscribe(
            {"type": "cash"},
            [{"amount": "6541.72", "currencyId": "EUR"}],
        )

    async def instrument_details(self, isin):
        return self._subscribe(
            {"type": "instrument", "id": isin},
            {"shortName": isin, "exchangeIds": ["LSX"]},
        )

    async def ticker(self, isin, exchange="LSX"):
        prices = {
            "IE00B57X3V84": "100.00",
            "XF000ETH0019": "4000.00",
        }
        return self._subscribe(
            {"type": "ticker", "id": f"{isin}.{exchange}"},
            {"last": {"price": prices[isin]}},
        )

    def _subscribe(self, subscription, response):
        self.counter += 1
        subscription_id = f"sub-{self.counter}"
        self.subscriptions[subscription_id] = subscription
        self.responses[subscription_id] = response
        return subscription_id

    async def recv(self):
        subscription_id = next(iter(self.subscriptions))
        return subscription_id, self.subscriptions[subscription_id], self.responses[subscription_id]

    async def unsubscribe(self, subscription_id):
        self.subscriptions.pop(subscription_id, None)


class FakeSecAccountPortfolioApi(FakePortfolioApi):
    def __init__(self):
        super().__init__()
        self.portfolio_payloads = []

    def settings(self):
        return {"securitiesAccountNumber": "SEC-123"}

    async def subscribe(self, payload):
        self.portfolio_payloads.append(payload)
        return self._subscribe(
            payload,
            {
                "positions": [
                    {"instrumentId": "IE00B57X3V84", "netSize": "31.293027", "averageBuyIn": "79.922"},
                    {"instrumentId": "XF000ETH0019", "netSize": "0.0076", "averageBuyIn": "3807.6711"},
                ]
            },
        )


class FakePortfolioByTypeApi(FakeSecAccountPortfolioApi):
    async def subscribe(self, payload):
        if payload["type"] == "compactPortfolio":
            self.portfolio_payloads.append(payload)
            return self._subscribe(
                payload,
                "BAD_SUBSCRIPTION_TYPE: Unknown topic type: compactPortfolio.31",
            )
        return await super().subscribe(payload)

    async def recv(self):
        subscription_id = next(iter(self.subscriptions))
        subscription = self.subscriptions[subscription_id]
        response = self.responses[subscription_id]
        if subscription.get("type") == "compactPortfolio":
            raise Exception(response)
        return subscription_id, subscription, response


class FakeGroupedPortfolioByTypeApi(FakeSecAccountPortfolioApi):
    async def subscribe(self, payload):
        self.portfolio_payloads.append(payload)
        if payload["type"] == "compactPortfolio":
            response = {"positions": []}
        else:
            response = {
                "portfolios": [
                    {
                        "portfolioType": "SECURITIES",
                        "positions": [
                            {"instrumentId": "IE00B57X3V84", "netSize": "31.293027", "averageBuyIn": "79.922"},
                            {"instrumentId": "XF000ETH0019", "netSize": "0.0076", "averageBuyIn": "3807.6711"},
                        ],
                    }
                ]
            }
        return self._subscribe(payload, response)


class FakeEmptyPortfolioApi(FakeSecAccountPortfolioApi):
    async def subscribe(self, payload):
        self.portfolio_payloads.append(payload)
        return self._subscribe(payload, {"positions": []})


def test_fetch_all_transactions_mock_filters_date_range():
    original_mode = settings.app_mode
    settings.app_mode = "mock"

    try:
        items = trade_republic.fetch_all_transactions(
            from_date="2026-04-16",
            to_date="2026-04-16",
        )
    finally:
        settings.app_mode = original_mode

    assert [item["id_externe"] for item in items] == ["af05b58b-1608-44fe-802f-ccf8123853f1"]


def test_filter_timestamp_to_date_is_inclusive():
    start = trade_republic._filter_timestamp("2026-04-16")
    end = trade_republic._filter_timestamp("2026-04-16", end_of_day=True)

    assert end > start
    assert end - start == 24 * 60 * 60


def test_paginated_history_follows_cursor_and_filters_range():
    api = FakeTimelineApi()

    items, meta = asyncio.run(trade_republic._fetch_timeline_transactions_paginated(
        api,
        from_date="2026-04-16",
        to_date="2026-04-16",
    ))

    assert [item["id"] for item in items] == ["wanted"]
    assert api.after_values == [None, "cursor-2"]
    assert meta["pages_read"] == 2
    assert meta["items_returned"] == 1


def test_extract_depot_value_sums_compact_portfolio_net_values():
    summary = trade_republic._extract_depot_value({
        "positions": [
            {"instrumentId": "A", "netValue": "123.45"},
            {"instrumentId": "B", "netValue": 76.55},
        ]
    })

    assert summary["depot_value"] == 200.0
    assert summary["positions"] == 2
    assert summary["valued_positions"] == 2


def test_extract_depot_value_falls_back_to_size_times_price():
    summary = trade_republic._extract_depot_value({
        "positions": [
            {"instrumentId": "A", "netSize": "2.5", "price": "10.00"},
            {"instrumentId": "B", "netSize": "3", "price": {"value": 1234, "fractionDigits": 2}},
        ]
    })

    assert summary["depot_value"] == 62.02
    assert summary["positions"] == 2
    assert summary["valued_positions"] == 2


def test_fetch_depot_value_summary_enriches_prices_from_tickers():
    summary = asyncio.run(trade_republic._fetch_depot_value_summary(FakePortfolioApi()))

    assert summary["depot_value"] == 3159.70
    assert summary["cash_value"] == 6541.72
    assert summary["total_value"] == 9701.42
    assert summary["positions"] == 2
    assert summary["valued_positions"] == 2


def test_fetch_depot_value_summary_sends_securities_account_number():
    api = FakeSecAccountPortfolioApi()
    summary = asyncio.run(trade_republic._fetch_depot_value_summary(api))

    assert api.portfolio_payloads == [{"type": "compactPortfolio", "secAccNo": "SEC-123"}]
    assert summary["depot_value"] == 3159.70
    assert summary["positions"] == 2
    assert summary["valued_positions"] == 2


def test_fetch_depot_value_summary_falls_back_to_compact_portfolio_by_type():
    api = FakePortfolioByTypeApi()
    summary = asyncio.run(trade_republic._fetch_depot_value_summary(api))

    assert api.portfolio_payloads == [
        {"type": "compactPortfolio", "secAccNo": "SEC-123"},
        {"type": "compactPortfolioByType", "secAccNo": "SEC-123"},
    ]
    assert summary["depot_value"] == 3159.70
    assert summary["positions"] == 2
    assert summary["valued_positions"] == 2


def test_fetch_depot_value_summary_unpacks_grouped_portfolio_by_type():
    api = FakeGroupedPortfolioByTypeApi()
    summary = asyncio.run(trade_republic._fetch_depot_value_summary(api))

    assert api.portfolio_payloads == [
        {"type": "compactPortfolio", "secAccNo": "SEC-123"},
        {"type": "compactPortfolioByType", "secAccNo": "SEC-123"},
    ]
    assert summary["depot_value"] == 3159.70
    assert summary["positions"] == 2
    assert summary["valued_positions"] == 2


def test_fetch_depot_value_summary_rejects_empty_portfolio_responses():
    api = FakeEmptyPortfolioApi()

    with pytest.raises(ValueError, match="keine auswertbaren Depotpositionen"):
        asyncio.run(trade_republic._fetch_depot_value_summary(api))

    assert api.portfolio_payloads == [
        {"type": "compactPortfolio", "secAccNo": "SEC-123"},
        {"type": "compactPortfolioByType", "secAccNo": "SEC-123"},
    ]
