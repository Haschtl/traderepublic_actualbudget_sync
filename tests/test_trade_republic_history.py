from app.core.config import settings
from app.services import trade_republic


class FakeApi:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def resume_websession(self):
        return True

    def timeline_transactions(self, after=None):
        return after

    def run_blocking(self, after, timeout=30):
        self.calls.append(after)
        return self.pages[after]


def test_fetch_all_transactions_keeps_following_cursor_after_empty_page(monkeypatch, tmp_path):
    original_mode = settings.app_mode
    original_cookies = settings.tr_cookies_file
    settings.app_mode = "production"
    settings.tr_cookies_file = str(tmp_path / "pytr_cookies.json")

    pages = {
        None: {"items": [], "cursors": {"after": "next"}},
        "next": {
            "items": [
                {
                    "id": "old-item",
                    "timestamp": "2025-01-01T10:00:00.000+0000",
                    "amount": {"currency": "EUR", "value": 1, "fractionDigits": 2},
                    "status": "EXECUTED",
                    "eventType": "INTEREST_PAYOUT",
                }
            ],
            "cursors": {},
        },
    }
    fake_api = FakeApi(pages)

    monkeypatch.setattr(trade_republic, "SESSIONS", {
        "sid": {"status": "connected", "cookies_file": str(tmp_path / "sid.cookies.json")}
    })
    monkeypatch.setattr(trade_republic, "_load_sessions", lambda: None)
    monkeypatch.setattr(trade_republic, "_get_api_client", lambda sid: fake_api)
    monkeypatch.setattr(trade_republic, "_store_api_client", lambda sid, api: None)
    monkeypatch.setattr(trade_republic, "_reset_api_async_state", lambda api: None)

    try:
        items = trade_republic.fetch_all_transactions("sid")
    finally:
        settings.app_mode = original_mode
        settings.tr_cookies_file = original_cookies

    assert fake_api.calls == [None, "next"]
    assert [item["id"] for item in items] == ["old-item"]
