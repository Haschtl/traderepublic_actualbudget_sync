# Trade Republic → Actual Budget Sync

Service **FastAPI** permettant de synchroniser les transactions **Trade Republic** vers **Actual Budget** via les bibliothèques [`pytr`](https://github.com/pytr-org/pytr) et [`actualpy`](https://github.com/bvanelli/actualpy).

---

## Sommaire

- [Déploiement rapide (Docker)](#déploiement-rapide-docker)
- [Variables d'environnement](#variables-denvironnement)
- [Premier démarrage — Authentification TR](#premier-démarrage--authentification-tr)
- [Synchronisation des transactions](#synchronisation-des-transactions)
- [Référence des endpoints](#référence-des-endpoints)
- [Développement local](#développement-local)
- [Architecture](#architecture)

---

## Déploiement rapide (Docker)

L'image est publiée sur GitHub Container Registry :

```
ghcr.io/aielloine/traderepublic_actualbudget_sync:latest
```

### 1. Récupérer les fichiers de déploiement

```bash
mkdir tr-sync && cd tr-sync
curl -O https://raw.githubusercontent.com/aielloine/traderepublic_actualbudget_sync/main/docker/docker-compose.yml
curl -O https://raw.githubusercontent.com/aielloine/traderepublic_actualbudget_sync/main/docker/.env.example
cp .env.example .env
```

### 2. Configurer le fichier `.env`

Éditez `.env` avec vos informations :

```env
APP_MODE=production

TR_PHONE_NUMBER=+33600000000
TR_PIN=1234

ACTUAL_URL=http://your-actual-server:5006
ACTUAL_PASSWORD=your-password
ACTUAL_BUDGET_ID=Mon Budget
ACTUAL_ACCOUNT_NAME=Trade Republic
```

> **Astuce** : Si vous ne connaissez pas votre `ACTUAL_BUDGET_ID`, laissez-le vide, démarrez le service, puis appelez `GET /actual/files` pour lister les budgets disponibles.

### 3. Démarrer le service

```bash
docker compose up -d
```

L'interface web est accessible sur **http://your-server:8000**.

---

## Variables d'environnement

| Variable             | Obligatoire | Description                                                           | Exemple                      |
|----------------------|:-----------:|-----------------------------------------------------------------------|------------------------------|
| `APP_MODE`           | ✅           | `production` ou `mock` (simule les API)                               | `production`                 |
| `TR_PHONE_NUMBER`    | ✅           | Numéro de téléphone Trade Republic (format international)             | `+33600000000`               |
| `TR_PIN`             | ✅           | Code PIN Trade Republic (4 chiffres)                                  | `1234`                       |
| `TR_COOKIES_FILE`    |             | Chemin du fichier de cookies TR (persistance de session)              | `/data/pytr_cookies.json`    |
| `ACTUAL_URL`         | ✅           | URL de votre instance Actual Budget                                   | `http://localhost:5006`      |
| `ACTUAL_PASSWORD`    |             | Mot de passe Actual Budget                                            | `my-secret`                  |
| `ACTUAL_BUDGET_ID`   | ✅           | Nom exact ou `file_id` du budget (voir `GET /actual/files`)           | `Mon Budget`                 |
| `ACTUAL_ACCOUNT_NAME`| ✅           | Nom exact du compte dans lequel importer les transactions             | `Trade Republic`             |

---

## Premier démarrage — Authentification TR

Trade Republic utilise un flux d'authentification en 2 étapes (code SMS ou notification mobile).

### Étape 1 — Démarrer le flux

Ouvrez l'interface web sur **http://your-server:8000** et cliquez sur **Se connecter à Trade Republic**, ou via curl :

```bash
curl -X POST http://your-server:8000/tr/connect
```

Réponse :
```json
{ "session_id": "abc123", "status": "pending" }
```

Trade Republic vous envoie un code PIN par SMS ou notification mobile.

### Étape 2 — Entrer le code reçu

```bash
curl -X POST http://your-server:8000/tr/complete \
  -H "Content-Type: application/json" \
  -d '{"code": "123456", "session_id": "abc123"}'
```

Réponse :
```json
{ "status": "connected" }
```

> Les cookies de session sont sauvegardés dans `TR_COOKIES_FILE`. Les prochains démarrages ne nécessitent pas de ré-authentification tant que la session reste valide.

---

## Synchronisation des transactions

Une fois authentifié, lancez une synchronisation complète :

```bash
curl -X POST http://your-server:8000/tr/sync \
  -H "Content-Type: application/json" \
  -d '{"session_id": "abc123"}'
```

Réponse :
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

Les transactions déjà présentes dans Actual Budget sont automatiquement détectées et ignorées grâce à `reconcile_transaction`.

---

## Référence des endpoints

| Méthode | Endpoint          | Description                                                    |
|---------|-------------------|----------------------------------------------------------------|
| `GET`   | `/health`         | Vérification que le service tourne                             |
| `GET`   | `/tr/status`      | Statut de la session Trade Republic en cours                   |
| `POST`  | `/tr/connect`     | Démarre le flux d'auth TR (envoie le code SMS/notification)    |
| `POST`  | `/tr/complete`    | Body: `{"code": "...", "session_id": "..."}` — valide le code  |
| `POST`  | `/tr/resend`      | Body: `{"session_id": "..."}` — renvoie un nouveau code        |
| `POST`  | `/tr/fetch`       | Body: `{"session_id": "..."}` — récupère les transactions TR   |
| `POST`  | `/tr/map`         | Body: liste de transactions pytr — retourne le mapping preview |
| `POST`  | `/tr/sync`        | Body: `{"session_id": "..."}` — fetch + map + push complet     |
| `GET`   | `/actual/files`   | Liste les budgets disponibles sur le serveur Actual Budget     |
| `GET`   | `/docs`           | Documentation interactive Swagger UI                           |

---

## Déploiement avec Actual Budget sur le même serveur

Si vous faites tourner Actual Budget via Docker sur le même serveur, utilisez ce `docker-compose.yml` combiné :

```yaml
services:
  actual-budget:
    image: docker.io/actualbudget/actual-server:latest
    ports:
      - "5006:5006"
    volumes:
      - actual_data:/data
    networks:
      - sync_network

  tr-sync:
    image: ghcr.io/aielloine/traderepublic_actualbudget_sync:latest
    ports:
      - "8000:8000"
    environment:
      APP_MODE: production
      TR_PHONE_NUMBER: "+33600000000"
      TR_PIN: "1234"
      TR_COOKIES_FILE: /data/pytr_cookies.json
      ACTUAL_URL: "http://actual-budget:5006"
      ACTUAL_PASSWORD: "votre-mot-de-passe"
      ACTUAL_BUDGET_ID: "Mon Budget"
      ACTUAL_ACCOUNT_NAME: "Trade Republic"
    volumes:
      - tr_data:/data
    depends_on:
      - actual-budget
    networks:
      - sync_network

volumes:
  actual_data:
  tr_data:

networks:
  sync_network:
```

---

## Développement local

```bash
# Cloner le repo
git clone https://github.com/aielloine/traderepublic_actualbudget_sync.git
cd traderepublic_actualbudget_sync

# Créer l'environnement virtuel
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt

# Configurer l'environnement
cp docker/.env.example .env
# Éditer .env...

# Lancer en mode développement
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Lancer les tests
pytest tests/
```

---

## Architecture

```
app/
├── api/
│   └── routes.py          # Endpoints FastAPI
├── core/
│   └── config.py          # Variables d'environnement
├── mapping/
│   └── mapper.py          # Transformation TR → Actual
├── models/
│   └── schemas.py         # Schémas Pydantic
├── services/
│   ├── trade_republic.py  # Auth et fetch via pytr
│   └── actual.py          # Push vers Actual via actualpy
└── static/
    └── index.html         # Interface web minimaliste
docker/
├── docker-compose.yml     # Exemple de déploiement
└── .env.example           # Template de configuration
```
