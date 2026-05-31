from typing import List, Dict, Any
from datetime import datetime
import json


def _parse_date(tx: Dict[str, Any]) -> str:
    """Extrait et formate la date depuis un item TR réel ou mock."""
    # Format mock: tx["date"]; format réel TR: tx["timestamp"]
    iso_str = tx.get("date") or tx.get("timestamp") or (tx.get("raw") or {}).get("timestamp") or ""
    if not iso_str:
        return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.date().isoformat()
    except Exception:
        return iso_str[:10]


def _parse_amount(tx: Dict[str, Any]) -> int:
    """Retourne le montant en centimes entier.

    Gère les trois formes :
    - Format réel TR : tx["amount"] = {"currency": "EUR", "value": -37, "fractionDigits": 2}
    - Format mock pré-traité : tx["amount"] = "-4.87" (string)
    - Format mock avec raw : tx["raw"]["amount"]["value"]
    """
    value = None

    # 1. Format réel TR : amount est un dict
    amount_field = tx.get("amount")
    if isinstance(amount_field, dict):
        value = amount_field.get("value")

    # 2. Format mock pré-traité : amount est déjà string ou float
    if value is None:
        if isinstance(amount_field, (int, float)):
            value = float(amount_field)
        elif isinstance(amount_field, str):
            normalized = (
                amount_field.strip()
                .replace("€", "")
                .replace(" ", "")
            )

            # deutsches Format
            if "," in normalized:
                normalized = normalized.replace(".", "").replace(",", ".")
            try:
                value = float(normalized)
            except Exception:
                value = 0.0

    # 3. Fallback : raw.amount.value (format mock avec raw)
    if value is None:
        raw = tx.get("raw") or {}
        raw_amount = raw.get("amount") if isinstance(raw, dict) else None
        if isinstance(raw_amount, dict):
            value = raw_amount.get("value")

    try:
        return int(round(float(value) * 100))
    except Exception:
        return 0


def _extract_currency(tx: Dict[str, Any]) -> str:
    """Extrait la devise depuis l'item."""
    # Format réel TR : amount.currency
    amount_field = tx.get("amount")
    if isinstance(amount_field, dict):
        return amount_field.get("currency") or "EUR"
    # Format mock
    if tx.get("currency"):
        return tx["currency"]
    # Fallback raw
    raw = tx.get("raw") or {}
    if isinstance(raw, dict) and isinstance(raw.get("amount"), dict):
        return raw["amount"].get("currency") or "EUR"
    return "EUR"


def _extract_payee(tx: Dict[str, Any]) -> str:
    title = tx.get("title") or ""
    if title:
        return title
    raw = tx.get("raw") or {}
    if isinstance(raw, dict):
        return raw.get("title") or ""
    return ""


def _extract_source_id(tx: Dict[str, Any]) -> str | None:
    """Format réel TR : tx["id"]. Format mock : tx["id_externe"] ou raw.id."""
    return (
        tx.get("id_externe")
        or tx.get("id")
        or ((tx.get("raw") or {}).get("id") if isinstance(tx.get("raw"), dict) else None)
    )


def _extract_event_type(tx: Dict[str, Any]) -> str:
    raw = tx.get("raw") or {}
    raw_event_type = raw.get("eventType") if isinstance(raw, dict) else None
    return tx.get("eventType") or raw_event_type or tx.get("type") or ""


def _looks_like_transfer(tx: Dict[str, Any], event_type: str, payee: str) -> bool:
    haystack = " ".join(
        str(value or "")
        for value in [
            event_type,
            payee,
            tx.get("subtitle"),
            tx.get("category"),
            tx.get("type"),
        ]
    ).upper()
    transfer_markers = (
        "TRANSFER",
        "DEPOSIT",
        "WITHDRAW",
        "EINZAHL",
        "AUSZAHL",
        "SEPA",
        "CASH_IN",
        "CASH_OUT",
    )
    return any(marker in haystack for marker in transfer_markers)


def _build_memo(tx: Dict[str, Any], event_type: str, status: str) -> str:
    parts = []
    subtitle = tx.get("subtitle")
    if subtitle:
        parts.append(str(subtitle))
    if event_type:
        parts.append(f"TR eventType: {event_type}")
    if status:
        parts.append(f"TR status: {status}")

    try:
        details = json.dumps(tx, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        details = str(tx)
    parts.append("Trade Republic raw: " + details)
    return "\n".join(parts)


def map_pytr_to_actual(transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Mappe les items TR (format réel ou mock) vers le schéma Actual.

    Règles :
    - Filtrer status sauf EXECUTED/PENDING
    - Date → YYYY-MM-DD (depuis 'date' ou 'timestamp')
    - Montant → entier en centimes
    - payee ← title
    - eventType + détails TR complets → memo
    - source_id ← id ou id_externe
    """
    out = []
    for tx in transactions:
        status = (tx.get("status") or "").upper()
        if status and status not in {"EXECUTED", "PENDING"}:
            continue

        date = _parse_date(tx)
        amount = _parse_amount(tx)
        payee = _extract_payee(tx) or "(unknown)"
        source_id = _extract_source_id(tx)
        currency = _extract_currency(tx)
        event_type = _extract_event_type(tx)
        pending = status == "PENDING"
        cleared = status == "EXECUTED"

        out.append({
            "date": date,
            "payee": payee,
            "amount": amount,
            "currency": currency,
            "memo": _build_memo(tx, event_type, status),
            "source_id": source_id,
            "event_type": event_type,
            "cleared": cleared,
            "pending": pending,
            "is_transfer": _looks_like_transfer(tx, event_type, payee),
        })
    return out
