import csv
import io
from decimal import Decimal, InvalidOperation
from typing import Dict, List


CSV_EVENT_TYPE_MAP = {
    "BANK_TRANSACTION_INCOMING": "BANK_TRANSACTION_INCOMING",
    "CUSTOMER_INBOUND": "BANK_TRANSACTION_INCOMING",
    "CUSTOMER_INPAYMENT": "BANK_TRANSACTION_INCOMING",
    "TRANSFER_INBOUND": "BANK_TRANSACTION_INCOMING",
    "BANK_TRANSACTION_OUTGOING": "BANK_TRANSACTION_OUTGOING",
    "CUSTOMER_OUTBOUND": "BANK_TRANSACTION_OUTGOING",
    "TRANSFER_OUTBOUND": "BANK_TRANSACTION_OUTGOING",
    "TRANSFER_INSTANT_OUTBOUND": "BANK_TRANSACTION_OUTGOING",
    "TRADING_TRADE_EXECUTED": "TRADING_TRADE_EXECUTED",
    "INTEREST_PAYOUT": "INTEREST_PAYOUT",
    "CARD_TRANSACTION": "CARD_TRANSACTION",
    "TAX_OPTIMIZATION": "TAX_OPTIMIZATION",
}


def _parse_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    normalized = str(value).strip()
    if not normalized:
        return None
    normalized = normalized.replace("€", "").replace(" ", "")
    if "," in normalized and "." not in normalized:
        normalized = normalized.replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation:
        return None


def _classify_csv_event(row: Dict[str, str]) -> str:
    tx_type = (row.get("type") or "").strip().upper()
    category = (row.get("category") or "").strip().upper()
    asset_class = (row.get("asset_class") or "").strip()
    shares = (row.get("shares") or "").strip()

    if tx_type in CSV_EVENT_TYPE_MAP:
        return CSV_EVENT_TYPE_MAP[tx_type]
    if "INTEREST" in tx_type:
        return "INTEREST_PAYOUT"
    if "CARD" in tx_type:
        return "CARD_TRANSACTION"
    if shares or asset_class or tx_type in {"BUY", "SELL", "ORDER_BUY", "ORDER_SELL", "TRADE"}:
        return "TRADING_TRADE_EXECUTED"
    if category == "CASH":
        return tx_type or "CASH"
    return tx_type or category or "CSV_IMPORT"


def _signed_amount(row: Dict[str, str], event_type: str) -> Decimal:
    amount = _parse_decimal(row.get("amount")) or Decimal("0")
    tx_type = (row.get("type") or "").strip().upper()

    if event_type in {"BANK_TRANSACTION_INCOMING", "INTEREST_PAYOUT"}:
        return abs(amount)
    if event_type in {"BANK_TRANSACTION_OUTGOING", "CARD_TRANSACTION"}:
        return -abs(amount)
    if event_type == "TRADING_TRADE_EXECUTED":
        if "BUY" in tx_type:
            return -abs(amount)
        if "SELL" in tx_type:
            return abs(amount)
    return amount


def _display_name(row: Dict[str, str]) -> str:
    return (
        row.get("name")
        or row.get("counterparty_name")
        or row.get("description")
        or row.get("type")
        or "Trade Republic CSV"
    )


def parse_trade_republic_csv(csv_text: str) -> List[Dict]:
    """Parse the official Trade Republic CSV export into the pytr-like raw shape.

    The normal mapper then handles Actual account routing, transfer detection,
    duplicate IDs, and memo creation. The original CSV row is preserved under
    raw.csv so every exported detail lands in Actual notes.
    """
    reader = csv.DictReader(io.StringIO(csv_text.lstrip("\ufeff")))
    if not reader.fieldnames:
        return []

    items: List[Dict] = []
    for index, row in enumerate(reader, start=1):
        normalized = {str(k or "").strip(): (v or "").strip() for k, v in row.items()}
        event_type = _classify_csv_event(normalized)
        amount = _signed_amount(normalized, event_type)
        currency = normalized.get("currency") or normalized.get("original_currency") or "EUR"
        source_id = normalized.get("transaction_id") or f"tr-csv-{index}"
        description = normalized.get("description") or normalized.get("payment_reference") or ""

        items.append({
            "id": source_id,
            "timestamp": normalized.get("datetime") or normalized.get("date") or "",
            "date": normalized.get("date") or normalized.get("datetime") or "",
            "title": _display_name(normalized),
            "subtitle": description,
            "amount": {
                "currency": currency,
                "value": float(amount),
                "fractionDigits": 2,
            },
            "status": "EXECUTED",
            "eventType": event_type,
            "csvType": normalized.get("type") or "",
            "csvCategory": normalized.get("category") or "",
            "instrument": {
                "isin": normalized.get("symbol") or None,
                "name": normalized.get("name") or None,
            },
            "raw": {
                "id": source_id,
                "timestamp": normalized.get("datetime") or normalized.get("date") or "",
                "title": _display_name(normalized),
                "amount": {
                    "currency": currency,
                    "value": float(amount),
                    "fractionDigits": 2,
                },
                "status": "EXECUTED",
                "eventType": event_type,
                "csv": normalized,
            },
        })

    return items
