# TR → Actual Budget Sync

Backend minimal en Python/FastAPI pour récupérer des transactions Trade Republic (via `pytr`), les parser et les mapper vers le format attendu par Actual Budget.

Cette première version contient :
- un service FastAPI minimal
- un mapper `pytr` → `actual` (logique de mapping + filtrage)
- endpoints pour preview du mapping et hooks de récupération/synchronisation (modes mock)
- tests unitaires pour la fonction de mapping

Début rapide (Linux, bash):

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Endpoints utiles:
- GET /health
- POST /tr/map   — body: liste des transactions pytr; renvoie la preview mapped
- POST /tr/fetch — mode mock retourne un jeu d'exemples
- POST /tr/sync  — mappe et (en mode mock) simule un envoi vers Actual

Voir `.env.example` pour variables d'environnement attendues.

