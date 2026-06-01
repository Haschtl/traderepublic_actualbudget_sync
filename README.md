# Trade Republic → Actual Budget Sync

A **FastAPI** service for synchronizing **Trade Republic** transactions with **Actual Budget** using the [`pytr`](https://github.com/pytr-org/pytr) and [`actualpy`](https://github.com/bvanelli/actualpy) libraries.

---

## Table of Contents

- [Quick Start (Docker)](#quick-start-docker)
- [Environment Variables](#environment-variables)
- [First Startup — TR Authentication](#first-startup--tr-authentication)
- [Transaction Synchronization](#transaction-synchronization)
- [Endpoint Reference](#endpoint-reference)
- [Local Development](#local-development)
- [Architecture](#architecture)

---

## Quick Start (Docker)

The image is published on GitHub Container Registry:

```text
ghcr.io/haschtl/traderepublic_actualbudget_sync:latest
```

### 1. Download the deployment files

```bash
mkdir tr-sync && cd tr-sync
curl -O https://raw.githubusercontent.com/haschtl/traderepublic_actualbudget_sync/main/docker/docker-compose.yml
curl -O https://raw.githubusercontent.com/haschtl/traderepublic_actualbudget_sync/main/docker/.env.example
cp .env.example .env
```

### 2. Configure the `.env` file

Edit `.env` with your settings.

### 3. Start the service

```bash
docker compose up -d
```

The web interface is available at **http://your-server:8000**.

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| APP_MODE | ✅ | `production` or `mock` |
| SYNC_CRON | | Cron expression for automatic synchronization |
| BASIC_AUTH_USERNAME | | Optional Basic Auth username |
| BASIC_AUTH_PASSWORD | | Optional Basic Auth password |
| TR_PHONE_NUMBER | ✅ | Trade Republic phone number |
| TR_PIN | ✅ | Trade Republic PIN |
| TR_COOKIES_FILE | | Trade Republic cookie file |
| ACTUAL_URL | ✅ | Actual Budget server URL |
| ACTUAL_PASSWORD | | Actual server password |
| ACTUAL_ENCRYPTION_PASSWORD | | Budget encryption password |
| ACTUAL_BUDGET_ID | ✅ | Budget name or file ID |
| ACTUAL_CASH_ACCOUNT_NAME | ✅ | Cash account name |
| ACTUAL_DEPOT_ACCOUNT_NAME | ✅ | Depot account name |
| ACTUAL_TRANSFER_ACCOUNT_NAME | | Optional transfer account |
| TR_AUTOCREATE_TRANSFER | | Automatically create transfer counterparts |

---

## First Startup — TR Authentication

Trade Republic uses a two-step authentication flow (SMS code or mobile push notification).

### Step 1 — Start authentication

```bash
curl -X POST http://your-server:8000/tr/connect
```

Response:

```json
{ "session_id": "abc123", "status": "pending" }
```

### Step 2 — Submit the received code

```bash
curl -X POST http://your-server:8000/tr/complete \
  -H "Content-Type: application/json" \
  -d '{"code": "123456", "session_id": "abc123"}'
```

Response:

```json
{ "status": "connected" }
```

Session cookies are stored in `TR_COOKIES_FILE`.

---

## Transaction Synchronization

Once authenticated:

```bash
curl -X POST http://your-server:8000/tr/sync \
  -H "Content-Type: application/json" \
  -d '{"session_id": "abc123"}'
```

Response:

```json
{
  "mapped_count": 42,
  "pushed": {
    "status": "ok",
    "inserted": 5,
    "skipped": 0,
    "duplicates": 37
  }
}
```

Existing transactions are detected automatically through `reconcile_transaction` and skipped.

`ACTUAL_CASH_ACCOUNT_NAME` and `ACTUAL_DEPOT_ACCOUNT_NAME` are automatically created if they do not exist.

`EXECUTED` transactions are imported as cleared.

`PENDING` transactions are imported as pending.

Actual notes contain the TR event type, status, and raw Trade Republic transaction details.

### Trade Republic eventType mapping

- `BANK_TRANSACTION_INCOMING` / `BANK_TRANSACTION_OUTGOING`: cash transaction with optional transfer matching.
- `TRADING_TRADE_EXECUTED`: internal transfer between Trade Republic Cash and Trade Republic Depot.
- `INTEREST_PAYOUT`, `SSP_CORPORATE_ACTION_CASH`, `CARD_TRANSACTION`: regular cash transaction.
- All other event types: imported as cash transactions with raw Trade Republic details in notes.

For external bank transfers, the importer first searches for an existing unmatched transaction in `ACTUAL_TRANSFER_ACCOUNT_NAME` with the opposite amount and a date within ±3 days. If found, the transactions are linked as a transfer. Otherwise, no counterpart transaction is created by default.

Enable automatic creation with:

```env
TR_AUTOCREATE_TRANSFER=true
```

### Automatic Synchronization

The service also starts an internal scheduler.

Default:

```env
SYNC_CRON=0 1 * * *
```

Disable:

```env
SYNC_CRON=
```

Manual synchronization:

```bash
curl -X POST http://your-server:8000/tr/sync-now
```

---

## Encrypted Actual Budgets

If your Actual budget is encrypted, set:

```env
ACTUAL_ENCRYPTION_PASSWORD=your-budget-password
```

Then:

```bash
curl -X POST http://your-server:8000/actual/encrypt
```

Future synchronizations will automatically use this password.

---

## Endpoint Reference

| Method | Endpoint | Description |
|---------|----------|-------------|
| GET | `/health` | Verify that the service is running |
| GET | `/tr/status` | Current Trade Republic session status |
| POST | `/tr/connect` | Start the TR authentication flow |
| POST | `/tr/complete` | Validate authentication code |
| POST | `/tr/resend` | Send a new authentication code |
| POST | `/tr/fetch` | Fetch Trade Republic transactions |
| POST | `/tr/map` | Preview transaction mapping |
| POST | `/tr/sync` | Full fetch + map + push |
| POST | `/tr/sync-now` | Manual sync |
| POST | `/tr/sync-history` | Import historical transactions |
| GET | `/actual/files` | List available Actual budgets |
| POST | `/actual/encrypt` | Enable budget encryption |
| GET | `/docs` | Swagger UI |

---

## Local Development

```bash
git clone https://github.com/haschtl/traderepublic_actualbudget_sync.git
cd traderepublic_actualbudget_sync

python3 -m venv .venv
source .venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt

cp docker/.env.example .env

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pytest tests/
```

---

## Architecture

```text
app/
├── api/
│   └── routes.py          # FastAPI endpoints
├── core/
│   └── config.py          # Environment variables
├── mapping/
│   └── mapper.py          # TR → Actual transformation
├── models/
│   └── schemas.py         # Pydantic schemas
├── services/
│   ├── trade_republic.py  # Authentication and fetching via pytr
│   └── actual.py          # Push to Actual via actualpy
└── static/
    └── index.html         # Minimal web interface
```
