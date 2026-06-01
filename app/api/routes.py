from fastapi import APIRouter, HTTPException
import asyncio
from typing import List
from app.models.schemas import PytrTransaction, ActualTransaction
from app.mapping.mapper import map_pytr_to_actual
from app.services.trade_republic import fetch_transactions as tr_fetch
from app.services.trade_republic import (
    fetch_all_transactions as tr_fetch_history,
    get_last_history_meta,
    start_login as tr_start_login,
    complete_login as tr_complete_login,
    get_login_status as tr_get_status,
    resend_login as tr_resend_login,
    TRRateLimitError,
)
from typing import Optional
from app.services.actual import push_transactions as actual_push
from app.services.actual import list_budget_files as actual_list_files
from app.services.actual import encrypt_budget as actual_encrypt_budget
from app.services.actual import preview_import as actual_preview_import
from app.services.actual import reset_imported_transactions as actual_reset_import
from app.services.actual import adjust_depot_balance as actual_adjust_depot_balance
from app.services.scheduler import run_history_sync, run_scheduled_sync
from app.services.state import mark_sync_failure, mark_sync_success
from app.services.trade_republic_csv import parse_trade_republic_csv

router = APIRouter()


def _serialize_models(items):
    serialized = []
    for item in items:
        if hasattr(item, "model_dump"):
            serialized.append(item.model_dump())
        else:
            serialized.append(item.dict())
    return serialized


@router.post("/tr/map", response_model=List[ActualTransaction])
async def map_preview(transactions: List[PytrTransaction]):
    """Retourne la preview des transactions mappées (sans les envoyer)."""
    mapped = map_pytr_to_actual(_serialize_models(transactions))
    return mapped


@router.post("/tr/preview-import")
async def preview_import(transactions: List[ActualTransaction]):
    serialized = _serialize_models(transactions)
    try:
        return await asyncio.to_thread(actual_preview_import, serialized)
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tr/fetch")
async def fetch_from_tr(payload: Optional[dict] = None):
    session_id = (payload or {}).get("session_id") or None
    try:
        txs = await asyncio.to_thread(tr_fetch, session_id)
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    return {"count": len(txs), "transactions": txs}


@router.post("/tr/fetch-history")
async def fetch_history_from_tr(payload: Optional[dict] = None):
    payload = payload or {}
    session_id = payload.get("session_id") or None
    from_date = payload.get("from_date") or None
    to_date = payload.get("to_date") or None
    try:
        txs = await asyncio.to_thread(
            tr_fetch_history,
            session_id,
            from_date=from_date,
            to_date=to_date,
        )
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    return {
        "count": len(txs),
        "transactions": txs,
        "fetch_meta": get_last_history_meta(),
    }


@router.post("/tr/push-mapped")
async def push_mapped_to_actual(transactions: List[ActualTransaction]):
    serialized = _serialize_models(transactions)
    try:
        pushed = await asyncio.to_thread(actual_push, serialized)
        response = {"mapped_count": len(serialized), "pushed": pushed}
        mark_sync_success(response, scheduled=False)
        return response
    except Exception as e:
        mark_sync_failure(str(e), scheduled=False)
        raise



@router.post("/tr/connect")
async def tr_connect():
    """Démarre le flux d'authentification Trade Republic.

    En mode mock renvoie simplement status connected=true.
    Dans le cas réel, déclenche l'envoi du code SMS/notification TR.
    Retourne un 'session_id' à fournir dans /tr/complete et /tr/resend.
    Lève HTTP 429 si TR rate-limite les tentatives, HTTP 500 pour toute autre erreur.
    """
    try:
        resp = await asyncio.to_thread(tr_start_login)
    except TRRateLimitError as e:
        headers = {"Retry-After": str(e.retry_after)} if e.retry_after else {}
        raise HTTPException(status_code=429, detail=str(e), headers=headers or None)
    except (RuntimeError, NotImplementedError) as e:
        raise HTTPException(status_code=500, detail=str(e))
    return resp


@router.post("/tr/complete")
async def tr_complete(payload: dict):
    """Complète le connexion TR — attend un JSON contenant par ex. {'code': '123456', 'session_id': '...'}.
    Retourne le statut final ou une erreur.
    """
    code = payload.get("code") or payload.get("pin")
    session_id = payload.get("session_id")
    if not code:
        raise HTTPException(status_code=400, detail="Attendu un champ 'code' ou 'pin' dans le body")
    try:
        resp = await asyncio.to_thread(tr_complete_login, code, session_id)
    except TRRateLimitError as e:
        headers = {"Retry-After": str(e.retry_after)} if e.retry_after else {}
        raise HTTPException(status_code=429, detail=str(e), headers=headers or None)
    except NotImplementedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return resp


@router.post("/tr/resend")
async def tr_resend(payload: dict):
    """Redemande l'envoi du code TR pour une session déjà initiée.

    Body: {'session_id': '...'}
    """
    session_id = payload.get("session_id")
    if not session_id:
        raise HTTPException(status_code=400, detail="Attendu un champ 'session_id' dans le body")
    try:
        resp = await asyncio.to_thread(tr_resend_login, session_id)
    except TRRateLimitError as e:
        headers = {"Retry-After": str(e.retry_after)} if e.retry_after else {}
        raise HTTPException(status_code=429, detail=str(e), headers=headers or None)
    except NotImplementedError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return resp


@router.get("/actual/files")
async def list_actual_files():
    """Liste les fichiers budgets disponibles sur le serveur Actual.

    Utile pour trouver le bon ACTUAL_BUDGET_ID (file_id ou name exact)
    et les noms de comptes disponibles à mettre dans ACTUAL_ACCOUNT_NAME.
    """
    try:
        files = await asyncio.to_thread(actual_list_files)
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"files": files}


@router.post("/actual/encrypt")
async def encrypt_actual_budget():
    """Active le chiffrement du budget Actual configuré."""
    try:
        result = await asyncio.to_thread(actual_encrypt_budget)
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return result


@router.post("/actual/reset-tr-import")
async def reset_actual_tr_import(payload: Optional[dict] = None):
    payload = payload or {}
    dry_run = bool(payload.get("dry_run", True))
    try:
        return await asyncio.to_thread(actual_reset_import, dry_run)
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/actual/depot-adjustment")
async def adjust_actual_depot(payload: dict):
    target_value = payload.get("target_value")
    if target_value in (None, ""):
        raise HTTPException(status_code=400, detail="target_value fehlt.")
    date = payload.get("date") or None
    try:
        return await asyncio.to_thread(actual_adjust_depot_balance, target_value, date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/tr/status")
async def tr_status():
    return tr_get_status()


@router.post("/tr/sync")
async def sync_to_actual(payload: Optional[dict] = None):
    """Récupère, mappe, et pousse vers Actual (mode mock possible).
    Retourne un résumé de l'opération.
    """
    session_id = (payload or {}).get("session_id") or None
    try:
        txs = await asyncio.to_thread(tr_fetch, session_id)
        mapped = map_pytr_to_actual(txs)
        result = await asyncio.to_thread(actual_push, mapped)
        response = {"mapped_count": len(mapped), "pushed": result}
        mark_sync_success(response, scheduled=False)
        return response
    except Exception as e:
        mark_sync_failure(str(e), scheduled=False)
        raise


@router.post("/tr/sync-now")
async def sync_now():
    """Lance le même sync que le scheduler, avec verrou anti-parallèle."""
    return await run_scheduled_sync()


@router.post("/tr/sync-history")
async def sync_history(payload: Optional[dict] = None):
    """Récupère toute l'historique TR paginée, mappe, puis pousse vers Actual."""
    payload = payload or {}
    session_id = payload.get("session_id") or None
    from_date = payload.get("from_date") or None
    to_date = payload.get("to_date") or None
    return await run_history_sync(session_id, from_date=from_date, to_date=to_date)


@router.post("/tr/csv/preview")
async def preview_csv_import(payload: dict):
    csv_text = payload.get("csv") or ""
    if not csv_text.strip():
        raise HTTPException(status_code=400, detail="CSV fehlt.")
    txs = parse_trade_republic_csv(csv_text)
    mapped = map_pytr_to_actual(txs)
    preview = None
    preview_error = None
    try:
        preview = await asyncio.to_thread(actual_preview_import, mapped)
    except Exception as e:
        preview_error = str(e)
    response = {
        "source": "csv",
        "count": len(txs),
        "mapped_count": len(mapped),
        "transactions": txs,
        "mapped": mapped,
        "preview": preview,
    }
    if preview_error:
        response["preview_error"] = preview_error
    return response


@router.post("/tr/csv/sync")
async def sync_csv_import(payload: dict):
    csv_text = payload.get("csv") or ""
    if not csv_text.strip():
        raise HTTPException(status_code=400, detail="CSV fehlt.")
    try:
        txs = parse_trade_republic_csv(csv_text)
        mapped = map_pytr_to_actual(txs)
        pushed = await asyncio.to_thread(actual_push, mapped)
        response = {
            "source": "csv",
            "count": len(txs),
            "mapped_count": len(mapped),
            "pushed": pushed,
        }
        mark_sync_success(response, scheduled=False)
        return response
    except Exception as e:
        mark_sync_failure(str(e), scheduled=False)
        raise
