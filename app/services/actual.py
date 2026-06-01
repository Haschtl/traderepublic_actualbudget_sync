import datetime
import logging
from decimal import Decimal
from typing import List, Dict, Any

from app.core.config import settings

log = logging.getLogger(__name__)


def _is_truthy(value: Any) -> bool:
    return str(value).lower() in {"1", "true", "yes", "on"}


def _find_transaction_by_financial_id(session, imported_id: str | None):
    if not imported_id:
        return None
    try:
        from actual.database import Transactions
        from sqlmodel import select
    except ImportError:
        return None
    return session.exec(
        select(Transactions).where(Transactions.financial_id == imported_id, Transactions.tombstone == 0)
    ).first()


def _find_matching_transfer_counterpart(session, account, date: datetime.date, amount_eur: float):
    """Find an existing unlinked transaction that can become the other side of a transfer."""
    try:
        from actual.database import Transactions
        from actual.utils.conversions import date_to_int, decimal_to_cents
        from sqlmodel import select
    except ImportError:
        return None

    target_amount = decimal_to_cents(Decimal(str(amount_eur)))
    start = date_to_int(date - datetime.timedelta(days=3))
    end = date_to_int(date + datetime.timedelta(days=3))

    return session.exec(
        select(Transactions)
        .where(Transactions.acct == account.id)
        .where(Transactions.amount == target_amount)
        .where(Transactions.date >= start)
        .where(Transactions.date <= end)
        .where(Transactions.transferred_id.is_(None))
        .where(Transactions.tombstone == 0)
        .where(Transactions.is_parent == 0)
    ).first()


def _create_or_link_transfer(
    session,
    date: datetime.date,
    account,
    transfer_account,
    amount_eur: float,
    notes: str,
    imported_id: str | None,
    payee: str,
    cleared: bool,
    pending: bool,
    allow_create_pair: bool,
):
    from actual.queries import create_transaction, create_transaction_from_ids, create_transfer

    if amount_eur > 0:
        source_account = transfer_account
        dest_account = account
        transfer_amount = amount_eur
        main_amount = amount_eur
        counterpart_amount = -amount_eur
    else:
        source_account = account
        dest_account = transfer_account
        transfer_amount = abs(amount_eur)
        main_amount = amount_eur
        counterpart_amount = abs(amount_eur)

    existing_counterpart = _find_matching_transfer_counterpart(
        session,
        transfer_account,
        date,
        counterpart_amount,
    )

    if existing_counterpart is not None:
        main_tx = create_transaction_from_ids(
            session,
            date,
            account.id,
            transfer_account.payee.id,
            notes,
            None,
            main_amount,
            imported_id,
            cleared,
            payee,
            process_payee=False,
        )
        main_tx.pending = int(pending)
        existing_counterpart.transferred_id = main_tx.id
        main_tx.transferred_id = existing_counterpart.id
        existing_counterpart.payee_id = account.payee.id
        existing_counterpart.category_id = None
        existing_counterpart.notes = existing_counterpart.notes or notes
        existing_counterpart.cleared = int(cleared)
        existing_counterpart.pending = int(pending)
        if imported_id and not existing_counterpart.financial_id:
            existing_counterpart.financial_id = f"{imported_id}:counterpart"
        return main_tx, existing_counterpart, True
    if allow_create_pair:
        source_tx, dest_tx = create_transfer(
            session,
            date=date,
            source_account=source_account,
            dest_account=dest_account,
            amount=transfer_amount,
            notes=notes,
        )
        main_tx = dest_tx if amount_eur > 0 else source_tx
        counterpart_tx = source_tx if amount_eur > 0 else dest_tx
        main_tx.financial_id = imported_id
        counterpart_tx.financial_id = f"{imported_id}:counterpart" if imported_id else None
        main_tx.imported_description = payee
        counterpart_tx.imported_description = payee
        main_tx.cleared = int(cleared)
        counterpart_tx.cleared = int(cleared)
        main_tx.pending = int(pending)
        counterpart_tx.pending = int(pending)
        return main_tx, counterpart_tx, False

    main_tx = create_transaction(
        session,
        date=date,
        account=account,
        payee=payee,
        notes=notes,
        amount=main_amount,
        imported_id=imported_id,
        cleared=cleared,
        imported_payee=payee,
    )
    main_tx.pending = int(pending)
    main_tx.imported_description = payee
    return main_tx, None, False


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


def encrypt_budget() -> Dict[str, Any]:
    """Active le chiffrement du budget Actual configuré.

    Cette opération utilise ACTUAL_ENCRYPTION_PASSWORD comme mot de passe
    de chiffrement du fichier budget, distinct du mot de passe serveur.
    """
    if settings.app_mode == "mock":
        return {"status": "mocked", "encrypted": True}

    try:
        from actual import Actual
    except ImportError as e:
        raise NotImplementedError("Le package 'actualpy' est requis. Erreur: %s" % e)

    url = settings.actual_url
    password = settings.actual_password
    budget_id = settings.actual_budget_id
    encryption_password = settings.actual_encryption_password

    if not url:
        raise NotImplementedError("ACTUAL_URL non configuré. Ajoutez-le à votre .env.")
    if not budget_id:
        raise NotImplementedError("ACTUAL_BUDGET_ID non configuré. Ajoutez-le à votre .env.")
    if not encryption_password:
        raise NotImplementedError(
            "ACTUAL_ENCRYPTION_PASSWORD non configuré. "
            "Définissez-le avant d'activer le chiffrement du budget."
        )

    with Actual(
        base_url=url,
        password=password or None,
        file=budget_id,
        encryption_password=encryption_password,
    ) as actual:
        actual.encrypt(encryption_password)
        return {
            "status": "ok",
            "file_id": actual.file.file_id,
            "name": actual.file.name,
            "encrypted": True,
        }


def push_transactions(transactions: List[Dict]) -> Dict:
    """Pousse les transactions mappées vers Actual Budget.

    - En `APP_MODE=mock` : simule l'envoi, retourne un résumé.
    - En mode production : utilise `actualpy` (pip install actualpy).

    Variables d'environnement requises :
        ACTUAL_URL          URL du serveur Actual (ex : http://localhost:5006)
        ACTUAL_PASSWORD     Mot de passe Actual
        ACTUAL_ENCRYPTION_PASSWORD Mot de passe de chiffrement du budget (si activé)
        ACTUAL_BUDGET_ID    ID ou nom du budget (fichier)
        ACTUAL_ACCOUNT_NAME Nom du compte dans le budget (ex : "Trade Republic")
    """
    if settings.app_mode == "mock":
        return {"status": "mocked", "accepted": len(transactions)}

    if not transactions:
        return {"status": "ok", "inserted": 0, "skipped": 0}

    try:
        from actual import Actual
        from actual.queries import get_or_create_account, reconcile_transaction
    except ImportError as e:
        raise NotImplementedError(
            "Le package 'actualpy' est requis. Installez-le: pip install actualpy. Erreur: %s" % e
        )

    url = settings.actual_url
    password = settings.actual_password
    encryption_password = settings.actual_encryption_password
    budget_id = settings.actual_budget_id
    cash_account_name = settings.actual_cash_account_name
    depot_account_name = settings.actual_depot_account_name
    transfer_account_name = settings.actual_transfer_account_name

    if not url:
        raise NotImplementedError("ACTUAL_URL non configuré. Ajoutez-le à votre .env.")
    if not cash_account_name:
        raise NotImplementedError(
            "ACTUAL_CASH_ACCOUNT_NAME non configuré. "
            "Indiquez le nom exact du compte cash Actual cible dans votre .env."
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
            encryption_password=encryption_password or None,
        ) as actual:
            session = actual.session
            cash_account = get_or_create_account(session, cash_account_name)
            depot_account = get_or_create_account(session, depot_account_name)
            transfer_account = (
                get_or_create_account(session, transfer_account_name)
                if transfer_account_name
                else None
            )
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
                cleared = bool(tx.get("cleared"))
                pending = _is_truthy(tx.get("pending"))
                is_transfer = _is_truthy(tx.get("is_transfer"))
                transfer_kind = tx.get("transfer_kind")
                account = depot_account if tx.get("account_key") == "depot" else cash_account

                try:
                    if is_transfer and transfer_kind == "external" and transfer_account is not None and amount_eur:
                        if _find_transaction_by_financial_id(session, imported_id):
                            duplicates += 1
                            log.debug("Transfert doublon détecté et ignoré (imported_id=%s)", imported_id)
                            continue

                        result_tx, counterpart_tx, linked_existing = _create_or_link_transfer(
                            session,
                            date=date,
                            account=account,
                            transfer_account=transfer_account,
                            amount_eur=amount_eur,
                            notes=notes,
                            imported_id=imported_id,
                            payee=payee,
                            cleared=cleared,
                            pending=pending,
                            allow_create_pair=settings.autocreate_transfer,
                        )
                        inserted += 1
                        if linked_existing:
                            log.info(
                                "Transfert lié à une transaction existante du compte opposé (imported_id=%s)",
                                imported_id,
                            )
                        continue

                    if is_transfer and transfer_kind == "depot" and amount_eur:
                        if _find_transaction_by_financial_id(session, imported_id):
                            duplicates += 1
                            log.debug("Trade-Transfer doublon détecté et ignoré (imported_id=%s)", imported_id)
                            continue

                        trade_account = cash_account if amount_eur < 0 else depot_account
                        counterpart_account = depot_account if amount_eur < 0 else cash_account
                        result_tx, counterpart_tx, linked_existing = _create_or_link_transfer(
                            session,
                            date=date,
                            account=trade_account,
                            transfer_account=counterpart_account,
                            amount_eur=amount_eur,
                            notes=notes,
                            imported_id=imported_id,
                            payee=payee,
                            cleared=cleared,
                            pending=pending,
                            allow_create_pair=True,
                        )
                        inserted += 1
                        continue

                    result_tx = reconcile_transaction(
                        session,
                        date=date,
                        account=account,
                        payee=payee,
                        notes=notes,
                        amount=amount_eur,
                        imported_id=imported_id,
                        cleared=cleared,
                        imported_payee=payee,
                        update_existing=False,
                        already_matched=already_matched,
                    )
                    result_tx.pending = int(pending)
                    result_tx.cleared = int(cleared)
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
