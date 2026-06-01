from app.core.config import settings
from app.services import trade_republic
import asyncio


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
