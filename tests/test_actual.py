import datetime

from actual.database import Accounts, Transactions
from actual.utils.conversions import date_to_int
from sqlmodel import SQLModel, Session, create_engine

from app.services.actual import (
    _find_cross_source_import_duplicate,
    _find_existing_linked_transfer_duplicate,
    _find_trade_import_duplicate,
)


def test_cross_source_transfer_duplicate_requires_existing_import():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        account = Accounts(id="cash", name="Trade Republic Cash", offbudget=0, closed=0)
        imported = Transactions(
            id="imported",
            acct=account.id,
            date=date_to_int(datetime.date(2026, 3, 27)),
            amount=-300000,
            financial_id="019d30a1-0ce9-7b04-a8b8-3e8d1f82feee",
            notes='Trade Republic raw: {"timestamp": "2026-03-27T18:49:14.217972Z"}',
            tombstone=0,
            is_parent=0,
        )
        manual = Transactions(
            id="manual",
            acct=account.id,
            date=date_to_int(datetime.date(2026, 3, 28)),
            amount=-300000,
            financial_id=None,
            notes='Trade Republic raw: {"timestamp": "2026-03-28T18:49:14.217972Z"}',
            tombstone=0,
            is_parent=0,
        )
        separate_import = Transactions(
            id="separate-import",
            acct=account.id,
            date=date_to_int(datetime.date(2026, 3, 29)),
            amount=-300000,
            financial_id="another-source-id",
            notes='Trade Republic raw: {"timestamp": "2026-03-29T10:00:00.000Z"}',
            tombstone=0,
            is_parent=0,
        )
        session.add(account)
        session.add(imported)
        session.add(manual)
        session.add(separate_import)
        session.commit()

        match = _find_cross_source_import_duplicate(
            session,
            account,
            datetime.date(2026, 3, 27),
            -3000,
            'Trade Republic raw: {"timestamp": "2026-03-27T18:49:13.437+0000"}',
        )
        no_manual_match = _find_cross_source_import_duplicate(
            session,
            account,
            datetime.date(2026, 3, 28),
            -3000,
            'Trade Republic raw: {"timestamp": "2026-03-28T18:49:13.437+0000"}',
        )
        no_distant_timestamp_match = _find_cross_source_import_duplicate(
            session,
            account,
            datetime.date(2026, 3, 29),
            -3000,
            'Trade Republic raw: {"timestamp": "2026-03-29T12:00:00.000Z"}',
        )

        assert match.id == imported.id
        assert no_manual_match is None
        assert no_distant_timestamp_match is None


def test_existing_linked_transfer_is_detected_across_booking_dates():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        cash = Accounts(id="cash", name="Trade Republic Cash", offbudget=0, closed=0)
        bank = Accounts(id="bank", name="DKB", offbudget=0, closed=0)
        cash_side = Transactions(
            id="cash-side",
            acct=cash.id,
            date=date_to_int(datetime.date(2026, 6, 2)),
            amount=60000,
            transferred_id="bank-side",
            tombstone=0,
            is_parent=0,
        )
        bank_side = Transactions(
            id="bank-side",
            acct=bank.id,
            date=date_to_int(datetime.date(2026, 6, 2)),
            amount=-60000,
            transferred_id="cash-side",
            tombstone=0,
            is_parent=0,
        )
        session.add(cash)
        session.add(bank)
        session.add(cash_side)
        session.add(bank_side)
        session.commit()

        match = _find_existing_linked_transfer_duplicate(
            session,
            bank,
            cash,
            datetime.date(2026, 6, 3),
            600,
        )

        assert match.id == cash_side.id


def test_interest_payment_duplicate_is_detected_across_csv_and_api_ids():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        cash = Accounts(id="cash", name="Trade Republic Cash", offbudget=0, closed=0)
        existing = Transactions(
            id="interest",
            acct=cash.id,
            date=date_to_int(datetime.date(2026, 6, 1)),
            amount=1286,
            financial_id="019e8188-7c0b-790d-b5cb-2052e0cc344e",
            notes=(
                "TR eventType: INTEREST_PAYOUT\n"
                'Trade Republic raw: {"timestamp": "2026-06-01T04:54:26.059306Z"}'
            ),
            tombstone=0,
            is_parent=0,
        )
        session.add(cash)
        session.add(existing)
        session.commit()

        match = _find_cross_source_import_duplicate(
            session,
            cash,
            datetime.date(2026, 6, 1),
            12.86,
            'Trade Republic raw: {"id": "different-api-id", "timestamp": "2026-06-01T12:00:00.000Z"}',
            "INTEREST_PAYOUT",
        )

        assert match.id == existing.id


def test_trade_duplicate_uses_date_and_isin_when_timeline_amount_differs():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)

    with Session(engine) as session:
        cash = Accounts(id="cash", name="Trade Republic Cash", offbudget=0, closed=0)
        whole_shares = Transactions(
            id="csv-trade-whole",
            acct=cash.id,
            date=date_to_int(datetime.date(2026, 5, 12)),
            amount=-247659,
            financial_id="d1cde3a9-0a9c-4c60-bb22-b666802ed3da",
            notes=(
                "Buy trade IE00B57X3V84\n"
                "TR eventType: TRADING_TRADE_EXECUTED\n"
                'Trade Republic raw: {"csv": {"fee": "-1.00"}}'
            ),
            tombstone=0,
            is_parent=0,
        )
        fractional_shares = Transactions(
            id="csv-trade-fractional",
            acct=cash.id,
            date=date_to_int(datetime.date(2026, 5, 12)),
            amount=-2341,
            financial_id="aed6b632-826e-4fb9-ad48-eac09c1040c2",
            notes=(
                "Buy trade IE00B57X3V84\n"
                "TR eventType: TRADING_TRADE_EXECUTED"
            ),
            tombstone=0,
            is_parent=0,
        )
        session.add(cash)
        session.add(whole_shares)
        session.add(fractional_shares)
        session.commit()

        match = _find_trade_import_duplicate(
            session,
            cash,
            datetime.date(2026, 5, 12),
            -2501,
            "API trade amount: -2501.00, instrument: IE00B57X3V84",
        )

        assert match.id in {whole_shares.id, fractional_shares.id}
