from typing import List, Dict, Any
from datetime import datetime


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
            try:
                value = float(amount_field)
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


def map_pytr_to_actual(transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Mappe les items TR (format réel ou mock) vers le schéma Actual.

    Règles :
    - Filtrer status != 'EXECUTED'
    - Date → YYYY-MM-DD (depuis 'date' ou 'timestamp')
    - Montant → entier en centimes
    - payee ← title
    - subtitle → memo
    - source_id ← id ou id_externe
    """
    out = []
    for tx in transactions:
        status = (tx.get("status") or "").upper()
        if status and status != "EXECUTED":
            continue

        date = _parse_date(tx)
        amount = _parse_amount(tx)
        payee = _extract_payee(tx) or "(unknown)"
        memo = tx.get("subtitle") or ""
        source_id = _extract_source_id(tx)
        currency = _extract_currency(tx)

        out.append({
            "date": date,
            "payee": payee,
            "amount": amount,
            "currency": currency,
            "memo": memo,
            "source_id": source_id,
        })
    return out
