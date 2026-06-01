from app.core.config import settings
from app.services import trade_republic


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
