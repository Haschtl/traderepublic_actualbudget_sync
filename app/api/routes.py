from fastapi import APIRouter, HTTPException
import asyncio
from typing import List
from app.models.schemas import PytrTransaction, ActualTransaction
from app.mapping.mapper import map_pytr_to_actual
from app.services.trade_republic import fetch_transactions as tr_fetch
from app.services.trade_republic import (
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
from app.core.config import settings

router = APIRouter()


@router.post("/tr/map", response_model=List[ActualTransaction])
async def map_preview(transactions: List[PytrTransaction]):
    """Retourne la preview des transactions mappées (sans les envoyer)."""
    # Use model_dump for pydantic v2 when available, fallback to dict()
    serialized = []
    for t in transactions:
        if hasattr(t, "model_dump"):
            serialized.append(t.model_dump())
        else:
            serialized.append(t.dict())
    mapped = map_pytr_to_actual(serialized)
    return mapped


@router.post("/tr/fetch")
async def fetch_from_tr(payload: Optional[dict] = None):
    session_id = (payload or {}).get("session_id") or None
    try:
        txs = await asyncio.to_thread(tr_fetch, session_id)
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    return {"count": len(txs), "transactions": txs}



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
    Affiche également l'état de chiffrement de chaque fichier.
    """
    try:
        files = await asyncio.to_thread(actual_list_files)
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    return {"files": files}


@router.get("/tr/status")
async def tr_status():
    return tr_get_status()


@router.post("/tr/sync")
async def sync_to_actual(payload: Optional[dict] = None):
    """Récupère, mappe, et pousse vers Actual (mode mock possible).
    Retourne un résumé de l'opération.
    
    Si ACTUAL_ENCRYPTION_PASSWORD est défini, le budget sera chiffré avec AES-256-GCM.
    """
    session_id = (payload or {}).get("session_id") or None
    txs = await asyncio.to_thread(tr_fetch, session_id)
    mapped = map_pytr_to_actual(txs)
    result = await asyncio.to_thread(actual_push, mapped)
    return {"mapped_count": len(mapped), "pushed": result}


@router.post("/actual/encrypt")
async def encrypt_actual_budget(payload: Optional[dict] = None):
    """Chiffre le fichier budget Actual avec le mot de passe fourni.

    ⚠️ ATTENTION: Cette opération réinitialise le fichier sur le serveur.
    Assurez-vous d'avoir une copie locale avant d'exécuter.

    Body optionnel: {'encryption_password': '...'} 
    Si non fourni, utilisera ACTUAL_ENCRYPTION_PASSWORD de la configuration.

    Utilise AES-256-GCM (conforme à la spécification Actual Budget).

    Retourne:
        - status: "success"
        - message: Description du succès
        - algorithm: "AES-256-GCM"
        - file_id: ID du fichier chiffré
        - encrypt_key_id: ID de la clé de chiffrement
    """
    encryption_password = (payload or {}).get("encryption_password") or settings.actual_encryption_password
    
    if not encryption_password:
        raise HTTPException(
            status_code=400, 
            detail="Aucun mot de passe de chiffrement fourni. "
                   "Fournissez 'encryption_password' dans le body ou définissez ACTUAL_ENCRYPTION_PASSWORD."
        )
    
    try:
        result = await asyncio.to_thread(actual_encrypt_budget, encryption_password)
        return result
    except NotImplementedError as e:
        raise HTTPException(status_code=501, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
