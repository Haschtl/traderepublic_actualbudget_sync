# Trade Republic → Actual Budget Sync

A FastAPI service with a small web UI for importing Trade Republic transactions into Actual Budget.

It supports both the Trade Republic API via [`pytr`](https://github.com/pytr-org/pytr) and exported Trade Republic CSV files. Imports are previewed first, then pushed to Actual Budget in a second explicit step.

## Features

- Trade Republic login flow with persisted sessions/cookies.
- Two-step UI workflow:
  - Import from Trade Republic API or CSV and preview the mapping.
  - Push the currently previewed transactions to Actual Budget.
- Date-range history import from the Trade Republic timeline.
- CSV import fallback for exported Trade Republic transactions.
- Actual import preview with planned actions before anything is written.
- Automatic creation of two Actual accounts:
  - `Trade Republic Cash`
  - `Trade Republic Depot`
- Event-type based routing:
  - cash events go to the cash account.
  - executed trades create Cash ↔ Depot transfers.
  - external bank transfers can be matched against an existing Actual account.
- Transfer matching against `ACTUAL_TRANSFER_ACCOUNT_NAME`.
- Matched transfers are highlighted in the UI preview; hover shows the matched Actual transaction.
- Duplicate detection through Actual `financial_id`.
- Full Trade Republic details are written into Actual notes.
- Pending/cleared handling.
- Optional scheduled sync with cron syntax.
- Last-sync state stored on disk.
- Optional Basic Auth for UI/API.
- Actual encrypted budget support.

## Quick Start With Docker

The image is published on GitHub Container Registry:

```text
ghcr.io/haschtl/traderepublic_actualbudget_sync:latest
```

Download the deployment files:

```bash
mkdir tr-sync
cd tr-sync
curl -O https://raw.githubusercontent.com/haschtl/traderepublic_actualbudget_sync/main/docker/docker-compose.yml
curl -O https://raw.githubusercontent.com/haschtl/traderepublic_actualbudget_sync/main/docker/.env.example
cp .env.example .env
```

Edit `.env` or the compose environment values, then start:

```bash
docker compose up -d
```

The compose file exposes the UI on:

```text
http://127.0.0.1:8000
```

If you run it on a server, put a reverse proxy in front of it or change the bind address deliberately.

## Recommended UI Flow

Open `http://127.0.0.1:8000`.

1. Connect Trade Republic
   - Start TR login.
   - Enter the received code/PIN.
   - The backend stores session metadata and cookies next to `TR_COOKIES_FILE`.

2. Import and preview
   - `TR-Import`: fetches current API transactions.
   - `TR-Import` with a date range: fetches paginated history for that range.
   - `CSV-Import`: opens a file dialog and imports an exported Trade Republic CSV.

3. Review the Import Plan
   - See target Actual account.
   - See event type counts.
   - See planned actions such as insert, duplicate, linked transfer, or cash import without counterpart.
   - Transfer matches are highlighted; hover the row to see the matched Actual transaction.

4. Push to Actual
   - `Zu Actual pushen` only pushes the currently loaded/mapped preview.
   - It does not fetch Trade Republic again.

## Environment Variables

| Variable | Required | Default | Description |
| --- | --- | --- | --- |
| `APP_MODE` | yes | `mock` locally, `production` in docker example | `production` for real APIs, `mock` for local testing |
| `SYNC_CRON` | no | `0 1 * * *` | 5-field cron expression for scheduled sync; empty disables |
| `BASIC_AUTH_USERNAME` | no | empty | Enables Basic Auth when username and password are both set |
| `BASIC_AUTH_PASSWORD` | no | empty | Basic Auth password |
| `TR_PHONE_NUMBER` | production | empty | Trade Republic phone number |
| `TR_PIN` | production | empty | Trade Republic PIN |
| `TR_COOKIES_FILE` | no | `./pytr_cookies.json` | Persistent cookie path; session metadata is stored next to it |
| `ACTUAL_URL` | production | `http://localhost:5006` | Actual Budget server URL |
| `ACTUAL_PASSWORD` | no | empty | Actual server password |
| `ACTUAL_ENCRYPTION_PASSWORD` | if encrypted | empty | Actual budget encryption password |
| `ACTUAL_BUDGET_ID` | production | empty | Actual budget file ID or exact name |
| `ACTUAL_CASH_ACCOUNT_NAME` | yes | `Trade Republic Cash` | Actual cash account for TR cash transactions |
| `ACTUAL_DEPOT_ACCOUNT_NAME` | yes | `Trade Republic Depot` | Actual depot account for investments/trades |
| `ACTUAL_TRANSFER_ACCOUNT_NAME` | no | empty | Existing Actual account used to match external bank transfers |
| `TR_AUTOCREATE_TRANSFER` | no | `false` | If true, creates external transfer counterparts when no match exists |
| `TR_TRANSFER_MATCH_DAYS` | no | `3` | Date window for external transfer matching |
| `TR_TRANSFER_MATCH_TOLERANCE_CENTS` | no | `0` | Amount tolerance for external transfer matching |

## Account And Event Mapping

The importer uses two Trade Republic accounts inside Actual:

- `ACTUAL_CASH_ACCOUNT_NAME`
- `ACTUAL_DEPOT_ACCOUNT_NAME`

They are created automatically if missing.

Event mapping:

| Event type | Actual behavior |
| --- | --- |
| `BANK_TRANSACTION_INCOMING` | Cash account transaction; optional external transfer matching |
| `BANK_TRANSACTION_OUTGOING` | Cash account transaction; optional external transfer matching |
| `TRADING_TRADE_EXECUTED` | Cash ↔ Depot transfer |
| `INTEREST_PAYOUT` | Regular cash transaction |
| `SSP_CORPORATE_ACTION_CASH` | Regular cash transaction |
| `CARD_TRANSACTION` | Regular cash transaction |
| `TAX_OPTIMIZATION` | Regular cash transaction |
| unknown/other | Regular cash transaction with raw details in notes |

CSV export types are normalized before mapping. Supported examples:

| CSV type | Normalized event type |
| --- | --- |
| `CUSTOMER_INPAYMENT` | `BANK_TRANSACTION_INCOMING` |
| `TRANSFER_INBOUND` | `BANK_TRANSACTION_INCOMING` |
| `TRANSFER_OUTBOUND` | `BANK_TRANSACTION_OUTGOING` |
| `TRANSFER_INSTANT_OUTBOUND` | `BANK_TRANSACTION_OUTGOING` |
| `TRADING_TRADE_EXECUTED` | `TRADING_TRADE_EXECUTED` |
| `INTEREST_PAYOUT` | `INTEREST_PAYOUT` |
| `CARD_TRANSACTION` | `CARD_TRANSACTION` |
| `TAX_OPTIMIZATION` | `TAX_OPTIMIZATION` |

## Transfer Matching

External transfers are only considered for:

- `BANK_TRANSACTION_INCOMING`
- `BANK_TRANSACTION_OUTGOING`

If `ACTUAL_TRANSFER_ACCOUNT_NAME` is configured, the preview/import looks in that account for an existing unmatched transaction with:

- opposite amount,
- date within `TR_TRANSFER_MATCH_DAYS`,
- amount tolerance `TR_TRANSFER_MATCH_TOLERANCE_CENTS`,
- no existing `transferred_id`.

When a match is found, the importer links the new Trade Republic side to the existing Actual transaction.

If no match exists, the default behavior is to import only the Trade Republic cash side. It does not create a fake counterpart unless explicitly enabled:

```env
TR_AUTOCREATE_TRANSFER=true
```

## Notes Written To Actual

Each imported transaction memo contains:

- original Trade Republic event type,
- status,
- subtitle/description if available,
- full raw Trade Republic payload,
- for CSV imports, the complete original CSV row.

For `TRADING_TRADE_EXECUTED`, the API import also tries to fetch `timelineDetailV2` so trade details such as instrument data, fees, tax, and order details can land in the notes when Trade Republic provides them.

## Scheduled Sync

The service starts an internal scheduler when `SYNC_CRON` is set.

Default:

```env
SYNC_CRON=0 1 * * *
```

Scheduled sync uses the last successful sync date as the next lower bound. Manual history import remains controlled by the UI date range.

Disable scheduled sync:

```env
SYNC_CRON=
```

Manual scheduler trigger:

```bash
curl -X POST http://127.0.0.1:8000/tr/sync-now
```

## API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/health` | Health check |
| `GET` | `/docs` | Swagger UI |
| `GET` | `/tr/status` | Session and sync status |
| `POST` | `/tr/connect` | Start Trade Republic login |
| `POST` | `/tr/complete` | Complete login with code |
| `POST` | `/tr/resend` | Resend login code |
| `POST` | `/tr/fetch` | Fetch current Trade Republic API transactions |
| `POST` | `/tr/fetch-history` | Fetch paginated Trade Republic history without pushing |
| `POST` | `/tr/map` | Map raw TR transactions to Actual transaction shape |
| `POST` | `/tr/preview-import` | Preview mapped transactions against Actual |
| `POST` | `/tr/push-mapped` | Push already mapped transactions to Actual |
| `POST` | `/tr/csv/preview` | Parse CSV, map it, and return Actual preview |
| `POST` | `/tr/csv/sync` | Legacy CSV parse + map + push endpoint |
| `POST` | `/tr/sync` | Legacy API fetch + map + push endpoint |
| `POST` | `/tr/sync-history` | Legacy API history fetch + map + push endpoint |
| `POST` | `/tr/sync-now` | Trigger scheduled sync logic immediately |
| `GET` | `/actual/files` | List Actual budget files |
| `POST` | `/actual/encrypt` | Enable/use budget encryption |

The web UI uses the explicit two-step endpoints: fetch/preview first, then `/tr/push-mapped`.

## Actual Budget Encryption

For encrypted budgets, set:

```env
ACTUAL_ENCRYPTION_PASSWORD=your-budget-password
```

You can call:

```bash
curl -X POST http://127.0.0.1:8000/actual/encrypt
```

Future Actual connections use the configured encryption password.

## Security Notes

- Use `BASIC_AUTH_USERNAME` and `BASIC_AUTH_PASSWORD` if the UI is reachable by anyone else.
- The Docker compose example binds to `127.0.0.1:8000` by default.
- Store cookies and state in a persistent private volume.
- Do not commit `.env`, cookie files, session JSON, or local data directories.
- The Docker image runs as an unprivileged user.
- Prefer a reverse proxy with TLS for remote access.

## Local Development

```bash
git clone https://github.com/haschtl/traderepublic_actualbudget_sync.git
cd traderepublic_actualbudget_sync

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

cp .env.example .env

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Run focused tests:

```bash
PYTHONPATH=. pytest tests/test_scheduler.py tests/test_mapping.py tests/test_trade_republic_history.py tests/test_trade_republic_csv.py -q
```

## Project Structure

```text
app/
├── api/
│   └── routes.py              # FastAPI endpoints
├── core/
│   └── config.py              # Environment variables
├── mapping/
│   └── mapper.py              # TR/CSV → Actual mapping
├── models/
│   └── schemas.py             # Pydantic schemas
├── services/
│   ├── actual.py              # Actual preview, transfer matching, push
│   ├── scheduler.py           # Cron scheduler
│   ├── state.py               # Last-sync state
│   ├── trade_republic.py      # pytr login and API fetching
│   └── trade_republic_csv.py  # CSV parser/normalizer
└── static/
    ├── favicon.png
    └── index.html             # Web UI
```
