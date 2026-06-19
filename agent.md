# AI Agent Instructions (Project: TR to Actual Budget Sync)

## 🎯 Project Goal
Create a containerized web application (Docker) with a user interface that can:
1. Fetch transactions from a Trade Republic account using the Python library `pytr`.
2. Display these transactions clearly in a web interface.
3. Send these transactions to an Actual Budget instance.
4. Build the Docker image automatically with GitHub Actions and push it to GitHub Container Registry (ghcr.io).

## 📚 Documentation and References
Use the following documentation for the implementation:

*   **Trade Republic API (pytr):**
    *   Official repository: [https://github.com/pytr-org/pytr](https://github.com/pytr-org/pytr)
*   **Actual Budget API:**
    *   Official docs (Node.js): [https://actualbudget.org/docs/api/](https://actualbudget.org/docs/api/)
    *   *Recommended Python alternative* `actualpy`: [https://github.com/bvanelli/actualpy](https://github.com/bvanelli/actualpy) (provides direct access to the Actual Budget database from Python).
    *   *REST API alternative* `actual-http-api`: [https://github.com/jhonderson/actual-http-api](https://github.com/jhonderson/actual-http-api)
*   **FastAPI:** [https://fastapi.tiangolo.com/](https://fastapi.tiangolo.com/)
*   **Docker:** [https://docs.docker.com/](https://docs.docker.com/)
*   **GitHub Actions (CI/CD):** [https://docs.github.com/en/actions](https://docs.github.com/en/actions)

## 🛠️ Recommended Stack
*   **Backend:** Python with FastAPI.
*   **Frontend:** Vanilla HTML/CSS/JS with TailwindCSS or a lightweight framework. Keep the UI simple and serve it from the backend.
*   **Infrastructure:** Docker and GitHub Actions publishing to `ghcr.io`.

## 📋 Implementation Tasks

### Step 1: Initialize the Backend (Python/FastAPI)
*   Set up a basic FastAPI project.
*   Create API routes to:
    *   Authenticate with Trade Republic using `pytr`, including phone and PIN/device login.
    *   Fetch transaction history.
    *   Authenticate with Actual Budget using the server URL, password, and budget sync ID.
    *   Push formatted transactions to Actual Budget using `actualpy` or HTTP requests.

### Step 2: Process and Map Data
*   Create a function that parses the JSON returned by `pytr`.
*   Filter canceled transactions such as `"status": "CANCELED"` or mark them visually.
*   Map Trade Republic data to the format expected by Actual Budget:
    *   `date` -> transaction date in YYYY-MM-DD format.
    *   `amount.value` -> amount in Actual Budget's integer representation.
    *   `title` or `raw.title` -> payee.
    *   `subtitle` -> notes/memo.

### Step 3: Create the User Interface
*   Create a simple dashboard page.
*   **Data display:** Show fetched transactions in a clear table with date, payee, amount, status, and TR category.
*   **Actions:**
    *   A "Connect Trade Republic" button with 2FA support when needed.
    *   A "Fetch transactions" button.
    *   A "Sync with Actual Budget" button.
*   Make progress and errors visible through notifications or alerts.

### Step 4: Dockerize
*   Write a `Dockerfile` based on `python:3.11-slim`.
*   Install dependencies from `requirements.txt`.
*   Expose the application port, such as 8000.
*   Ensure credentials and tokens come from environment variables.

### Step 5: Continuous Integration (GitHub Actions)
*   Create `.github/workflows/docker-publish.yml`.
*   Trigger the workflow on pushes to `main`.
*   Build and tag the Docker image, authenticate to `ghcr.io` with `GITHUB_TOKEN`, and push it.

---

## 📄 Reference Data (`pytr` Payload)

The backend should parse this transaction structure returned by `pytr`:
```json
[
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
    "instrument": {
      "isin": null,
      "name": "Electra Paris"
    },
    "raw": {
      "id": "1c263c75-45c6-5a7d-8ed3-8d43d445c180",
      "timestamp": "2026-04-20T08:52:15.398+0000",
      "title": "Electra Paris",
      "amount": {
        "currency": "EUR",
        "value": -4.87,
        "fractionDigits": 2
      },
      "status": "EXECUTED",
      "eventType": "CARD_TRANSACTION"
    }
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
    "instrument": {
      "isin": "IE00B3YCGJ38",
      "name": "S&P 500 USD (Acc)"
    },
    "raw": {
      "id": "af05b58b-1608-44fe-802f-ccf8123853f1",
      "timestamp": "2026-04-16T14:44:36.978+0000",
      "title": "S&P 500 USD (Acc)",
      "amount": {
        "currency": "EUR",
        "value": -37.0,
        "fractionDigits": 2
      },
      "status": "EXECUTED",
      "eventType": "TRADING_SAVINGSPLAN_EXECUTED"
    }
  }
]
```

Specific parsing rules:

    Process only transactions where "status" == "EXECUTED". Ignore "CANCELED".

    Use title or raw.title for the payee name.

    Use raw.eventType or type to distinguish card payments (CARD_TRANSACTION) from scheduled investments (TRADING_SAVINGSPLAN_EXECUTED).

🚀 Start Implementation

Read these instructions, propose the project directory structure, and implement steps 1 and 2 first. Ask for validation before proceeding to the UI and Docker deployment.
