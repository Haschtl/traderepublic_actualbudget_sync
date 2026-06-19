import datetime

from actual.database import Accounts, Transactions
from actual.utils.conversions import date_to_int
from sqlmodel import SQLModel, Session, create_engine

from app.services.actual import _find_cross_source_import_duplicate


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
        linked_import = Transactions(
            id="linked-import",
            acct=account.id,
            date=date_to_int(datetime.date(2026, 3, 30)),
            amount=-300000,
            financial_id="old-csv-source-id",
            transferred_id="existing-counterpart",
            notes='Trade Republic raw: {"timestamp": "2026-03-30T10:00:00.000Z"}',
            tombstone=0,
            is_parent=0,
        )
        session.add(account)
        session.add(imported)
        session.add(manual)
        session.add(separate_import)
        session.add(linked_import)
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
        linked_transfer_match = _find_cross_source_import_duplicate(
            session,
            account,
            datetime.date(2026, 3, 30),
            -3000,
            'Trade Republic raw: {"timestamp": "2026-03-30T12:00:00.000Z"}',
        )

        assert match.id == imported.id
        assert no_manual_match is None
        assert no_distant_timestamp_match is None
        assert linked_transfer_match.id == linked_import.id
