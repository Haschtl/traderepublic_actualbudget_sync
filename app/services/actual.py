import datetime
import logging
from typing import List, Dict, Any

from app.core.config import settings

log = logging.getLogger(__name__)


def list_budget_files() -> List[Dict[str, Any]]:
    """Retourne la liste des fichiers budgets disponibles sur le serveur Actual.

    Utile pour trouver le bon ACTUAL_BUDGET_ID / ACTUAL_ACCOUNT_NAME.
    """
    try:
        from actual import Actual
    except ImportError as e:
        raise NotImplementedError("Le package 'actualpy' est requis. Erreur: %s" % e)

    url = settings.actual_url
    password = settings.actual_password

    if not url:
        raise NotImplementedError("ACTUAL_URL non configuré.")

    with Actual(base_url=url, password=password or None) as actual:
        files = actual.list_user_files()
        return [
            {
                "file_id": f.file_id,
                "name": f.name,
                "group_id": getattr(f, "group_id", None),
                "deleted": f.deleted,
                "encrypted": getattr(f, "encrypt_key_id", None) is not None,
            }
            for f in files.data
            if not f.deleted
        ]


def push_transactions(transactions: List[Dict]) -> Dict:
    """Pousse les transactions mappées vers Actual Budget.

    - En `APP_MODE=mock` : simule l'envoi, retourne un résumé.
    - En mode production : utilise `actualpy` (pip install actualpy).

    Variables d'environnement requises :
        ACTUAL_URL          URL du serveur Actual (ex : http://localhost:5006)
        ACTUAL_PASSWORD     Mot de passe Actual
        ACTUAL_BUDGET_ID    ID ou nom du budget (fichier)
        ACTUAL_ACCOUNT_NAME Nom du compte dans le budget (ex : "Trade Republic")
    """
    if settings.app_mode == "mock":
        return {"status": "mocked", "accepted": len(transactions)}

    if not transactions:
        return {"status": "ok", "inserted": 0, "skipped": 0}

    try:
        from actual import Actual
        from actual.queries import reconcile_transaction
    except ImportError as e:
        raise NotImplementedError(
            "Le package 'actualpy' est requis. Installez-le: pip install actualpy. Erreur: %s" % e
        )

    url = settings.actual_url
    password = settings.actual_password
    budget_id = settings.actual_budget_id
    account_name = settings.actual_account_name

    if not url:
        raise NotImplementedError("ACTUAL_URL non configuré. Ajoutez-le à votre .env.")
    if not account_name:
        raise NotImplementedError(
            "ACTUAL_ACCOUNT_NAME non configuré. "
            "Indiquez le nom exact du compte Actual cible dans votre .env."
        )

    inserted = 0
    skipped = 0
    duplicates = 0
    errors = []

    try:
        with Actual(
            base_url=url,
            password=password or None,
            file=budget_id or None,
        ) as actual:
            session = actual.session
            already_matched = []

            for tx in transactions:
                date_str = tx.get("date") or ""
                if not date_str:
                    log.warning("Transaction sans date ignorée: %s", tx)
                    skipped += 1
                    continue

                try:
                    date = datetime.date.fromisoformat(date_str)
                except ValueError:
                    log.warning("Date invalide '%s', transaction ignorée", date_str)
                    skipped += 1
                    continue

                payee = tx.get("payee") or "(unknown)"
                notes = tx.get("memo") or ""
                # Le mapper stocke les montants en centimes (int).
                # actualpy attend des euros (float) → on divise par 100.
                amount_eur = (tx.get("amount") or 0) / 100
                imported_id = tx.get("source_id") or None

                try:
                    result_tx = reconcile_transaction(
                        session,
                        date=date,
                        account=account_name,
                        payee=payee,
                        notes=notes,
                        amount=amount_eur,
                        imported_id=imported_id,
                        cleared=True,
                        imported_payee=payee,
                        update_existing=False,
                        already_matched=already_matched,
                    )
                    already_matched.append(result_tx)

                    # Si la transaction est dans session.new, elle vient d'être créée.
                    # Sinon, c'était un match existant (doublon).
                    if result_tx in session.new:
                        inserted += 1
                    else:
                        duplicates += 1
                        log.debug("Doublon détecté et ignoré (imported_id=%s)", imported_id)

                except Exception as e:
                    log.error("Erreur lors du reconcile de la transaction %s: %s", imported_id, e)
                    errors.append({"source_id": imported_id, "error": str(e)})
                    skipped += 1

            actual.commit()

    except NotImplementedError:
        raise
    except Exception as e:
        # Tenter de lister les fichiers disponibles pour un meilleur diagnostic
        available = []
        try:
            available = list_budget_files()
        except Exception:
            pass

        hint = ""
        if available:
            names = [f"{f['name']} (file_id={f['file_id']})" for f in available]
            hint = " Fichiers disponibles sur le serveur : " + ", ".join(names) + "."
        else:
            hint = " Appelez GET /actual/files pour lister les budgets disponibles."

        raise NotImplementedError(
            "Impossible de se connecter à Actual Budget ou de trouver le fichier budget. "
            "Vérifiez ACTUAL_URL, ACTUAL_PASSWORD, ACTUAL_BUDGET_ID (nom ou file_id exact), ACTUAL_ACCOUNT_NAME."
            "%s Erreur originale: %s" % (hint, e)
        )

    result: Dict = {"status": "ok", "inserted": inserted, "skipped": skipped, "duplicates": duplicates}
    if errors:
        result["errors"] = errors
    return result
