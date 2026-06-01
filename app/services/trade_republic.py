from typing import List, Dict
from app.core.config import settings
import uuid
import json
import logging
from pathlib import Path
import threading
from datetime import date, datetime

log = logging.getLogger(__name__)


# Simple in-memory session store; persisted next to TR_COOKIES_FILE for survivability.
SESSIONS = {}
SESSIONS_LOCK = threading.RLock()
API_CLIENTS = {}
LEGACY_SESSIONS_PATH = Path('/tmp/ab_tr_2_tr_sessions.json')


def _normalize_phone_number(phone: str | None) -> str | None:
    """Normalise le numéro pour l'API TR.

    Règles pragmatiques :
    - conserve un numéro déjà en E.164 (`+...`)
    - supprime espaces / séparateurs usuels
    - convertit les formats FR mobiles courants vers `+33...`
      - `06XXXXXXXX` -> `+336XXXXXXXX`
      - `6XXXXXXXX`  -> `+336XXXXXXXX`
    - sinon retourne la chaîne nettoyée telle quelle
    """
    if not phone:
        return phone

    cleaned = (
        str(phone)
        .strip()
        .replace(" ", "")
        .replace("-", "")
        .replace(".", "")
        .replace("(", "")
        .replace(")", "")
    )

    if cleaned.startswith("+"):
        return cleaned

    if cleaned.startswith("00"):
        return "+" + cleaned[2:]

    if cleaned.isdigit():
        # French mobile/local heuristic
        if len(cleaned) == 10 and cleaned.startswith(("06", "07")):
            return "+33" + cleaned[1:]
        if len(cleaned) == 9 and cleaned.startswith(("6", "7")):
            return "+33" + cleaned

    return cleaned


def _atomic_write_json(path: Path, payload: Dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.parent.chmod(0o700)
    except Exception:
        pass
    tmp_path = path.with_suffix(path.suffix + '.tmp')
    tmp_path.write_text(json.dumps(payload))
    try:
        tmp_path.chmod(0o600)
    except Exception:
        pass
    tmp_path.replace(path)


def _sessions_dir() -> Path:
    cookies_path = Path(settings.tr_cookies_file or "./pytr_cookies.json")
    if cookies_path.suffix:
        return cookies_path.parent / f"{cookies_path.stem}_sessions"
    return cookies_path / "sessions"


def _sessions_path() -> Path:
    cookies_path = Path(settings.tr_cookies_file or "./pytr_cookies.json")
    if cookies_path.suffix:
        return cookies_path.parent / f"{cookies_path.stem}_sessions.json"
    return cookies_path / "sessions.json"


def _load_sessions():
    global SESSIONS
    with SESSIONS_LOCK:
        sessions_path = _sessions_path()
        source_path = sessions_path if sessions_path.exists() else LEGACY_SESSIONS_PATH
        if source_path.exists():
            try:
                SESSIONS = json.loads(source_path.read_text())
            except Exception:
                SESSIONS = {}
        else:
            SESSIONS = {}


def _save_sessions():
    with SESSIONS_LOCK:
        try:
            _atomic_write_json(_sessions_path(), SESSIONS)
        except Exception:
            pass


def _cookies_file_for_session(session_id: str) -> str:
    sessions_dir = _sessions_dir()
    sessions_dir.mkdir(parents=True, exist_ok=True)
    try:
        sessions_dir.chmod(0o700)
    except Exception:
        pass
    return str(sessions_dir / f'{session_id}.cookies.json')


def _init_session(session_id: str, status: str, message: str) -> Dict:
    data = {
        'status': status,
        'message': message,
        'cookies_file': _cookies_file_for_session(session_id),
    }
    with SESSIONS_LOCK:
        SESSIONS[session_id] = data
    return data


def _store_api_client(session_id: str, api):
    with SESSIONS_LOCK:
        API_CLIENTS[session_id] = api


def _get_api_client(session_id: str):
    with SESSIONS_LOCK:
        return API_CLIENTS.get(session_id)


def _build_api_client(cookies_file: str):
    from pytr.api import TradeRepublicApi

    try:
        return TradeRepublicApi(
            phone_no=_normalize_phone_number(settings.tr_phone) or None,
            pin=settings.tr_pin or None,
            save_cookies=True,
            cookies_file=cookies_file,
        )
    except Exception:
        return TradeRepublicApi()


def _load_cookies_into_client(api) -> bool:
    """Charge les cookies depuis le fichier dans la websession sans appeler settings().

    N'utilise PAS resume_websession() car celle-ci appelle settings(), ce qui retourne
    401 pendant la phase de challenge (avant complete_weblogin) et efface les cookies.
    """
    try:
        if api._save_cookies and api._cookies_file.exists():
            api._websession.cookies.load(ignore_discard=True)
            log.info("Cookies chargés depuis %s", api._cookies_file)
            return True
    except Exception as exc:
        log.warning("Impossible de charger les cookies depuis le fichier: %s", exc)
    return False


class TRRateLimitError(Exception):
    """Levée quand Trade Republic retourne un 429 Too Many Requests."""
    def __init__(self, message: str, retry_after: int | None = None):
        super().__init__(message)
        self.retry_after = retry_after


def _raise_if_rate_limited(exc: Exception):
    """Convertit un HTTPError 429 en TRRateLimitError avec Retry-After si dispo."""
    try:
        import requests
        if isinstance(exc, requests.exceptions.HTTPError):
            resp = exc.response
            if resp is not None and resp.status_code == 429:
                retry_after = None
                try:
                    retry_after = int(resp.headers.get("Retry-After", 0)) or None
                except Exception:
                    pass
                msg = (
                    "Trade Republic a bloqué les tentatives de connexion (429 Too Many Requests). "
                    "Attendez %s minutes avant de réessayer."
                    % (f"environ {retry_after // 60}" if retry_after else "30 à 60")
                )
                raise TRRateLimitError(msg, retry_after=retry_after) from exc
    except TRRateLimitError:
        raise
    except Exception:
        pass



_SAMPLE = [
    {
        "id_externe": "1c263c75-45c6-5a7d-8ed3-8d43d445c180",
        "date": "2026-04-20T08:52:15.398+0000",
        "amount": "-4.87",
        "currency": "EUR",
        "type": "CARD",
        "category": "Expense",
        "status": "EXECUTED",
        "title": "Electra Paris",
        "subtitle": "",
        "instrument": {"isin": None, "name": "Electra Paris"},
        "raw": {
            "id": "1c263c75-45c6-5a7d-8ed3-8d43d445c180",
            "timestamp": "2026-04-20T08:52:15.398+0000",
            "title": "Electra Paris",
            "amount": {"currency": "EUR", "value": -4.87, "fractionDigits": 2},
            "status": "EXECUTED",
            "eventType": "CARD_TRANSACTION",
        },
    },
    {
        "id_externe": "af05b58b-1608-44fe-802f-ccf8123853f1",
        "date": "2026-04-16T14:44:36.978+0000",
        "amount": "-37.0",
        "currency": "EUR",
        "type": "BUY",
        "category": "Investment",
        "status": "EXECUTED",
        "title": "S&P 500 USD (Acc)",
        "subtitle": "Sparplan ausgeführt",
        "instrument": {"isin": "IE00B3YCGJ38", "name": "S&P 500 USD (Acc)"},
        "raw": {
            "id": "af05b58b-1608-44fe-802f-ccf8123853f1",
            "timestamp": "2026-04-16T14:44:36.978+0000",
            "title": "S&P 500 USD (Acc)",
            "amount": {"currency": "EUR", "value": -37.0, "fractionDigits": 2},
            "status": "EXECUTED",
            "eventType": "TRADING_SAVINGSPLAN_EXECUTED",
        },
    },
]


def _find_connected_session() -> tuple[str | None, str | None]:
    """Retourne (session_id, cookies_file) de la dernière session 'connected' trouvée."""
    with SESSIONS_LOCK:
        for sid, data in reversed(list(SESSIONS.items())):
            if data.get("status") == "connected":
                return sid, data.get("cookies_file") or _cookies_file_for_session(sid)
    return None, None


def _reset_api_async_state(api) -> None:
    """Réinitialise l'état asyncio de l'instance API.

    asyncio.run() crée un nouveau event loop à chaque appel. Les variables de classe
    asyncio.Lock / _ws / subscriptions sont liées au premier loop et deviennent invalides
    dans un loop différent. On les écrase au niveau instance pour repartir propre.
    """
    import asyncio as _asyncio
    api._lock = _asyncio.Lock()
    api._ws = None
    api._subscription_id_counter = 1
    api._previous_responses = {}
    api.subscriptions = {}


def fetch_transactions(session_id: str | None = None) -> List[Dict]:
    """Récupère les transactions depuis Trade Republic.

    - En `APP_MODE=mock` retourne un jeu d'exemples embarqué.
    - En mode non-mock, réutilise le client authentifié lié au `session_id`
      (ou à la dernière session 'connected' si non fourni).

    La réponse websocket de `timelineTransactions` est :
        {"items": [...], "cursors": {"after": ...}, "startingTransactionId": ...}
    On retourne uniquement `items`.
    """
    if settings.app_mode == "mock":
        return _SAMPLE

    _load_sessions()

    resolved_sid = session_id
    cookies_file = None

    if not resolved_sid:
        resolved_sid, cookies_file = _find_connected_session()
        if not resolved_sid:
            raise NotImplementedError(
                "Aucune session Trade Republic active. "
                "Connectez-vous via /tr/connect puis /tr/complete avant de récupérer les transactions."
            )
        log.info("fetch_transactions: utilisation de la session connectée %s", resolved_sid)

    session = SESSIONS.get(resolved_sid, {})
    cookies_file = cookies_file or session.get("cookies_file") or _cookies_file_for_session(resolved_sid)

    api = _get_api_client(resolved_sid)
    if api is None:
        log.warning("fetch_transactions: instance API non trouvée en mémoire — reconstruction depuis cookies")
        api = _build_api_client(cookies_file)
        _store_api_client(resolved_sid, api)

    # Auth complète → resume_websession() est sûr ici (settings() retourne 200)
    if not api.resume_websession():
        log.warning("fetch_transactions: resume_websession a échoué; les cookies sont peut-être expirés")

    # Réinitialiser l'état asyncio avant chaque appel à run_blocking / asyncio.run().
    # Sans ça, le 2e appel lève "Task got Future attached to a different loop" parce que
    # asyncio.Lock (variable de classe) est lié au premier event loop créé par asyncio.run().
    _reset_api_async_state(api)

    try:
        # run_blocking(coro, timeout) == asyncio.run(_receive_one(coro, timeout))
        # _receive_one : await subscribe_coro → sub_id, puis attend la réponse WS.
        # La réponse est un dict : {"items": [...], "cursors": {...}, "startingTransactionId": "..."}
        response = api.run_blocking(api.timeline_transactions(), timeout=30)
        log.info("fetch_transactions: réponse reçue, type=%s", type(response).__name__)

        if isinstance(response, dict):
            items = response.get("items", [])
        elif isinstance(response, list):
            items = response
        else:
            log.warning("fetch_transactions: format de réponse inattendu: %s", response)
            items = []

        log.info("fetch_transactions: %d transaction(s) récupérée(s)", len(items))
        return items

    except Exception as e:
        raise NotImplementedError(
            "Échec lors de la récupération des transactions Trade Republic. "
            "Vérifiez la session et la connexion. Erreur: %s" % e
        )


def _parse_filter_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value[:10])


def _transaction_date(item: Dict) -> date | None:
    raw_value = item.get("date") or item.get("timestamp") or (item.get("raw") or {}).get("timestamp")
    if not raw_value:
        return None
    try:
        return datetime.fromisoformat(str(raw_value).replace("Z", "+00:00")).date()
    except Exception:
        try:
            return date.fromisoformat(str(raw_value)[:10])
        except Exception:
            return None


def fetch_all_transactions(
    session_id: str | None = None,
    max_pages: int = 1000,
    from_date: str | None = None,
    to_date: str | None = None,
) -> List[Dict]:
    """Récupère toute l'historique disponible via la pagination timelineTransactions."""
    if settings.app_mode == "mock":
        start = _parse_filter_date(from_date)
        end = _parse_filter_date(to_date)
        return [
            item for item in _SAMPLE
            if ((tx_date := _transaction_date(item)) is None)
            or ((start is None or tx_date >= start) and (end is None or tx_date <= end))
        ]

    _load_sessions()

    resolved_sid = session_id
    cookies_file = None

    if not resolved_sid:
        resolved_sid, cookies_file = _find_connected_session()
        if not resolved_sid:
            raise NotImplementedError(
                "Aucune session Trade Republic active. "
                "Connectez-vous via /tr/connect puis /tr/complete avant de récupérer les transactions."
            )
        log.info("fetch_all_transactions: utilisation de la session connectée %s", resolved_sid)

    session = SESSIONS.get(resolved_sid, {})
    cookies_file = cookies_file or session.get("cookies_file") or _cookies_file_for_session(resolved_sid)

    api = _get_api_client(resolved_sid)
    if api is None:
        log.warning("fetch_all_transactions: instance API non trouvée en mémoire — reconstruction depuis cookies")
        api = _build_api_client(cookies_file)
        _store_api_client(resolved_sid, api)

    if not api.resume_websession():
        log.warning("fetch_all_transactions: resume_websession a échoué; les cookies sont peut-être expirés")

    items: list[Dict] = []
    seen_ids: set[str] = set()
    after = None
    start = _parse_filter_date(from_date)
    end = _parse_filter_date(to_date)

    try:
        for page in range(1, max_pages + 1):
            _reset_api_async_state(api)
            response = api.run_blocking(api.timeline_transactions(after), timeout=30)
            if not isinstance(response, dict):
                log.warning("fetch_all_transactions: format de réponse inattendu page %s: %s", page, response)
                break

            page_items = response.get("items") or []
            log.info("fetch_all_transactions: page %s reçue avec %d transaction(s)", page, len(page_items))

            page_dates = []
            for item in page_items:
                tx_date = _transaction_date(item)
                if tx_date:
                    page_dates.append(tx_date)
                if start and tx_date and tx_date < start:
                    continue
                if end and tx_date and tx_date > end:
                    continue
                item_id = item.get("id")
                if item_id and item_id in seen_ids:
                    continue
                if item_id:
                    seen_ids.add(item_id)
                items.append(item)

            cursors = response.get("cursors") or {}
            next_after = cursors.get("after")
            if not next_after or next_after == after:
                break
            if start and page_dates and max(page_dates) < start:
                break
            after = next_after
        else:
            log.warning("fetch_all_transactions: max_pages=%s atteint, historique possiblement incomplet", max_pages)

        log.info("fetch_all_transactions: %d transaction(s) récupérée(s) au total", len(items))
        return items

    except Exception as e:
        raise NotImplementedError(
            "Échec lors de la récupération de l'historique Trade Republic. "
            "Vérifiez la session et la connexion. Erreur: %s" % e
        )


def start_login() -> Dict:
    """Démarre le flux d'authentification Trade Republic.

    En mode mock renvoie simplement status connected=true.
    Dans le cas réel, tente d'utiliser TradeRepublicApi.initiate_weblogin() si disponible.
    """
    _load_sessions()
    sid = str(uuid.uuid4())

    if settings.app_mode == "mock":
        _init_session(sid, "connected", "mock connected")
        _save_sessions()
        return {"session_id": sid, "status": "connected", "message": "mock connected"}

    try:
        from pytr.api import TradeRepublicApi
    except Exception as e:
        raise NotImplementedError("pytr n'est pas installé; installez-le et adaptez start_login. Erreur: %s" % e)

    session = _init_session(sid, "pending", "started")
    cookies_file = session["cookies_file"]

    api = _build_api_client(cookies_file)
    _store_api_client(sid, api)
    _save_sessions()

    try:
        if hasattr(api, 'initiate_weblogin'):
            # initiate_weblogin is synchronous in pytr. It is already executed in a worker thread
            # from the FastAPI route, so call it directly once.
            countdown = api.initiate_weblogin()
            log.info("weblogin initié, process_id=%s, countdown=%s", api._process_id, countdown)
            # Save cookies right away so the fallback path (api lost from memory) can reload them.
            try:
                api.save_websession()
            except Exception as exc:
                log.warning("save_websession après initiate_weblogin a échoué: %s", exc)
            with SESSIONS_LOCK:
                SESSIONS[sid].update({
                    "status": "challenge",
                    "message": "weblogin initiated",
                    "process_id": getattr(api, "_process_id", None),
                    "phone": _normalize_phone_number(settings.tr_phone) or None,
                    "countdown": countdown,
                })
            _save_sessions()
            return {
                "session_id": sid,
                "status": "challenge",
                "message": "weblogin initiated — code envoyé par SMS/notification",
                "countdown_seconds": countdown,
            }
    except Exception as e:
        _raise_if_rate_limited(e)
        log.error("initiate_weblogin a échoué: %s", e, exc_info=True)
        with SESSIONS_LOCK:
            SESSIONS[sid].update({"status": "error", "message": str(e)})
        _save_sessions()
        raise RuntimeError("Échec de l'initiation du weblogin TR: %s" % e) from e

    raise NotImplementedError("initiate_weblogin absent de pytr. Adaptez app/services/trade_republic.py.")


def complete_login(code: str, session_id: str | None = None) -> Dict:
    """Complète le connexion TR — attend un code/pin et tente complete_weblogin."""
    _load_sessions()

    if settings.app_mode == "mock":
        sid = session_id or str(uuid.uuid4())
        if sid not in SESSIONS:
            _init_session(sid, "connected", "mock connected via code")
        else:
            with SESSIONS_LOCK:
                SESSIONS[sid].update({"status": "connected", "message": "mock connected via code"})
        _save_sessions()
        return {"session_id": sid, "status": "connected", "message": "mock connected"}

    try:
        from pytr.api import TradeRepublicApi
    except Exception as e:
        raise NotImplementedError("pytr n'est pas installé; installez-le et adaptez complete_login. Erreur: %s" % e)

    if not session_id:
        raise NotImplementedError("'session_id' est requis pour compléter un weblogin déjà initié.")

    session = SESSIONS.get(session_id)
    if not session:
        raise NotImplementedError("Session introuvable/expirée. Refaire /tr/connect puis /tr/complete avec le session_id renvoyé.")

    cookies_file = session.get('cookies_file') or _cookies_file_for_session(session_id)

    api = _get_api_client(session_id)
    if api is None:
        log.warning(
            "Instance API introuvable en mémoire pour session %s — "
            "reconstruction depuis cookies_file (le conteneur a peut-être redémarré).",
            session_id,
        )
        api = _build_api_client(cookies_file)
        _store_api_client(session_id, api)
        # Charger les cookies manuellement — on NE DOIT PAS appeler resume_websession()
        # car elle invoque settings() qui retourne 401 pendant la phase challenge et
        # efface les cookies, invalidant le flow en cours.
        _load_cookies_into_client(api)
    else:
        log.info("Instance API retrouvée en mémoire pour session %s", session_id)

    process_id = session.get("process_id")
    if process_id:
        setattr(api, "_process_id", process_id)
        log.info("complete_login: process_id=%s, session_id=%s", process_id, session_id)
    else:
        raise NotImplementedError("Session invalide: process_id absent. Refaire /tr/connect.")

    try:
        # During challenge completion, do NOT call resume_websession() — it calls settings()
        # which returns 401 and clears the cookies needed for complete_weblogin.
        if hasattr(api, 'complete_weblogin'):
            # complete_weblogin is synchronous in pytr and the route already runs in a worker thread.
            api.complete_weblogin(code)
            log.info("complete_weblogin réussi pour session %s", session_id)
            with SESSIONS_LOCK:
                SESSIONS[session_id].update({"status": "connected", "message": "via complete_weblogin"})
            _save_sessions()
            return {
                "session_id": session_id,
                "status": SESSIONS[session_id]["status"],
                "message": SESSIONS[session_id]["message"],
            }
    except Exception as e:
        _raise_if_rate_limited(e)
        log.error("complete_weblogin a échoué pour session %s: %s", session_id, e, exc_info=True)
        with SESSIONS_LOCK:
            SESSIONS[session_id].update({"status": "error", "message": str(e)})
        _save_sessions()
        raise NotImplementedError("Impossible de compléter l'authentification automatiquement. Erreur: %s" % e)

    raise NotImplementedError("Aucune méthode connue pour compléter la connexion (complete_weblogin absent). Adaptez app/services/trade_republic.py.")


def get_login_status() -> Dict:
    _load_sessions()
    sid, _cookies_file = _find_connected_session()
    return {
        "current_session_id": sid,
        "session_store": str(_sessions_path()),
        "sessions": SESSIONS,
    }


def resend_login(session_id: str) -> Dict:
    """Redemande l'envoi du code TR pour une session en état 'challenge'."""
    _load_sessions()

    if settings.app_mode == "mock":
        return {"session_id": session_id, "status": "challenge", "message": "mock resend"}

    try:
        from pytr.api import TradeRepublicApi  # noqa: F401
    except Exception as e:
        raise NotImplementedError("pytr n'est pas installé. Erreur: %s" % e)

    session = SESSIONS.get(session_id)
    if not session:
        raise NotImplementedError("Session introuvable/expirée. Refaire /tr/connect.")

    if session.get("status") != "challenge":
        raise NotImplementedError("La session n'est pas en attente de code (status=%s)." % session.get("status"))

    api = _get_api_client(session_id)
    if api is None:
        cookies_file = session.get("cookies_file") or _cookies_file_for_session(session_id)
        api = _build_api_client(cookies_file)
        _store_api_client(session_id, api)
        _load_cookies_into_client(api)

    process_id = session.get("process_id")
    if process_id:
        setattr(api, "_process_id", process_id)
    else:
        raise NotImplementedError("process_id absent. Refaire /tr/connect.")

    try:
        if hasattr(api, 'resend_weblogin'):
            api.resend_weblogin()
            log.info("resend_weblogin réussi pour session %s", session_id)
            return {"session_id": session_id, "status": "challenge", "message": "code renvoyé"}
    except Exception as e:
        _raise_if_rate_limited(e)
        log.error("resend_weblogin a échoué pour session %s: %s", session_id, e, exc_info=True)
        raise NotImplementedError("Échec du renvoi du code: %s" % e)

    raise NotImplementedError("resend_weblogin absent de pytr.")
