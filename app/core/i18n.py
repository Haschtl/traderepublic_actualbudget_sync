from contextvars import ContextVar, Token
from typing import Any


DEFAULT_LANGUAGE = "de"
SUPPORTED_LANGUAGES = ("de", "en")

_language: ContextVar[str] = ContextVar("language", default=DEFAULT_LANGUAGE)

TRANSLATIONS = {
    "de": {
        "api.code_required": "Im Request-Body wird das Feld 'code' oder 'pin' erwartet.",
        "api.session_id_required": "Im Request-Body wird das Feld 'session_id' erwartet.",
        "tr.rate_limited": "Trade Republic hat die Anmeldeversuche blockiert (429 Too Many Requests). Bitte {wait} Minuten warten und erneut versuchen.",
        "tr.wait_unknown": "30 bis 60",
        "tr.no_active_session_depot": "Keine aktive Trade-Republic-Session. Bitte zuerst über /tr/connect und /tr/complete anmelden, bevor der Depotwert abgerufen wird.",
        "tr.no_active_session_transactions": "Keine aktive Trade-Republic-Session. Bitte zuerst über /tr/connect und /tr/complete anmelden, bevor Transaktionen abgerufen werden.",
        "tr.session_expired": "Die Trade-Republic-Session ist abgelaufen oder konnte nicht wiederhergestellt werden. Bitte in der Oberfläche neu verbinden.",
        "tr.depot_fetch_failed": "Der Trade-Republic-Depotwert konnte nicht abgerufen werden. Bitte Session und Verbindung prüfen. Fehler: {error}",
        "tr.transactions_fetch_failed": "Die Trade-Republic-Transaktionen konnten nicht abgerufen werden. Bitte Session und Verbindung prüfen. Fehler: {error}",
        "tr.history_fetch_failed": "Der Trade-Republic-Verlauf konnte nicht abgerufen werden. Bitte Session und Verbindung prüfen. Fehler: {error}",
        "tr.pytr_missing": "pytr ist nicht installiert. Bitte Abhängigkeiten installieren. Fehler: {error}",
        "tr.login_started": "Anmeldung gestartet. Code per SMS oder Benachrichtigung gesendet.",
        "tr.login_start_failed": "Die Trade-Republic-Anmeldung konnte nicht gestartet werden. Fehler: {error}",
        "tr.login_method_missing": "pytr stellt initiate_weblogin nicht bereit.",
        "tr.login_session_required": "Für den Abschluss einer gestarteten Anmeldung ist 'session_id' erforderlich.",
        "tr.session_not_found": "Session nicht gefunden oder abgelaufen. Bitte /tr/connect erneut ausführen.",
        "tr.invalid_session_process": "Ungültige Session: process_id fehlt. Bitte /tr/connect erneut ausführen.",
        "tr.login_complete_failed": "Die Anmeldung konnte nicht automatisch abgeschlossen werden. Fehler: {error}",
        "tr.login_complete_method_missing": "pytr stellt keine bekannte Methode zum Abschluss der Anmeldung bereit.",
        "tr.session_not_waiting": "Die Session wartet nicht auf einen Code (Status: {status}).",
        "tr.code_resent": "Code erneut gesendet.",
        "tr.code_resend_failed": "Der Code konnte nicht erneut gesendet werden. Fehler: {error}",
        "tr.code_resend_method_missing": "pytr stellt resend_weblogin nicht bereit.",
        "actual.encryption_password_missing": "ACTUAL_ENCRYPTION_PASSWORD ist nicht konfiguriert. Bitte vor dem Aktivieren der Verschlüsselung setzen.",
        "actual.connection_failed": "Verbindung zu Actual Budget fehlgeschlagen oder Budgetdatei nicht gefunden. Bitte ACTUAL_URL, ACTUAL_PASSWORD, ACTUAL_BUDGET_ID und ACTUAL_ACCOUNT_NAME prüfen.",
    },
    "en": {
        "api.code_required": "The request body must contain a 'code' or 'pin' field.",
        "api.session_id_required": "The request body must contain a 'session_id' field.",
        "tr.rate_limited": "Trade Republic blocked the login attempts (429 Too Many Requests). Wait {wait} minutes and try again.",
        "tr.wait_unknown": "30 to 60",
        "tr.no_active_session_depot": "No active Trade Republic session. Sign in through /tr/connect and /tr/complete before fetching the portfolio value.",
        "tr.no_active_session_transactions": "No active Trade Republic session. Sign in through /tr/connect and /tr/complete before fetching transactions.",
        "tr.session_expired": "The Trade Republic session expired or could not be restored. Reconnect in the user interface.",
        "tr.depot_fetch_failed": "Could not fetch the Trade Republic portfolio value. Check the session and connection. Error: {error}",
        "tr.transactions_fetch_failed": "Could not fetch Trade Republic transactions. Check the session and connection. Error: {error}",
        "tr.history_fetch_failed": "Could not fetch the Trade Republic history. Check the session and connection. Error: {error}",
        "tr.pytr_missing": "pytr is not installed. Install the dependencies. Error: {error}",
        "tr.login_started": "Login started. Code sent by SMS or notification.",
        "tr.login_start_failed": "Could not start the Trade Republic login. Error: {error}",
        "tr.login_method_missing": "pytr does not provide initiate_weblogin.",
        "tr.login_session_required": "A 'session_id' is required to complete an initiated login.",
        "tr.session_not_found": "Session not found or expired. Run /tr/connect again.",
        "tr.invalid_session_process": "Invalid session: process_id is missing. Run /tr/connect again.",
        "tr.login_complete_failed": "Could not complete authentication automatically. Error: {error}",
        "tr.login_complete_method_missing": "pytr does not provide a known method for completing authentication.",
        "tr.session_not_waiting": "The session is not waiting for a code (status: {status}).",
        "tr.code_resent": "Code sent again.",
        "tr.code_resend_failed": "Could not resend the code. Error: {error}",
        "tr.code_resend_method_missing": "pytr does not provide resend_weblogin.",
        "actual.encryption_password_missing": "ACTUAL_ENCRYPTION_PASSWORD is not configured. Set it before enabling encryption.",
        "actual.connection_failed": "Could not connect to Actual Budget or find the budget file. Check ACTUAL_URL, ACTUAL_PASSWORD, ACTUAL_BUDGET_ID, and ACTUAL_ACCOUNT_NAME.",
    },
}


def normalize_language(value: str | None) -> str:
    if not value:
        return DEFAULT_LANGUAGE
    for part in value.lower().split(","):
        language = part.split(";", 1)[0].strip().split("-", 1)[0]
        if language in SUPPORTED_LANGUAGES:
            return language
    return DEFAULT_LANGUAGE


def set_language(value: str | None) -> Token:
    return _language.set(normalize_language(value))


def reset_language(token: Token) -> None:
    _language.reset(token)


def get_language() -> str:
    return _language.get()


def tr(key: str, **values: Any) -> str:
    language = get_language()
    template = TRANSLATIONS.get(language, TRANSLATIONS[DEFAULT_LANGUAGE]).get(key)
    if template is None:
        template = TRANSLATIONS[DEFAULT_LANGUAGE].get(key, key)
    return template.format(**values)
