# Instructions pour l'Agent IA (Projet : TR to Actual Budget Sync)

## 🎯 Objectif du Projet
Créer une application web conteneurisée (Docker) avec une interface utilisateur (UI) permettant de :
1. Récupérer les transactions d'un compte Trade Republic via la librairie Python `pytr`.
2. Afficher ces transactions clairement sur une interface web.
3. Envoyer ces transactions vers une instance "Actual Budget".
4. Automatiser la construction de l'image Docker via GitHub Actions (CI) et la pousser sur le GitHub Container Registry (ghcr.io).

## 📚 Documentations et Références
L'agent doit s'appuyer sur les documentations suivantes pour l'implémentation :

*   **Trade Republic API (pytr) :**
    *   Repo officiel : [https://github.com/pytr-org/pytr](https://github.com/pytr-org/pytr)
*   **Actual Budget API :**
    *   Docs Officielles (Node.js) : [https://actualbudget.org/docs/api/](https://actualbudget.org/docs/api/)
    *   *Alternative Python (Recommandée)* `actualpy` : [https://github.com/bvanelli/actualpy](https://github.com/bvanelli/actualpy) (Permet de manipuler la BDD Actual Budget directement en Python).
    *   *Alternative REST API* `actual-http-api` : [https://github.com/jhonderson/actual-http-api](https://github.com/jhonderson/actual-http-api)
*   **FastAPI :** [https://fastapi.tiangolo.com/](https://fastapi.tiangolo.com/)
*   **Docker :** [https://docs.docker.com/](https://docs.docker.com/)
*   **GitHub Actions (CI/CD) :** [https://docs.github.com/en/actions](https://docs.github.com/en/actions)

## 🛠️ Stack Technique Recommandée
*   **Backend :** Python avec FastAPI (idéal car `pytr` est en Python, FastAPI est léger et performant).
*   **Frontend :** HTML/CSS/JS Vanilla avec TailwindCSS (ou un framework léger). L'UI doit rester simple et servie par le backend.
*   **Infrastructure :** Docker, GitHub Actions pour publier sur `ghcr.io`.

## 📋 Tâches à réaliser (Étape par Étape)

### Étape 1 : Initialisation du Backend (Python/FastAPI)
*   Mettre en place un projet FastAPI de base.
*   Créer les routes d'API pour :
    *   S'authentifier sur Trade Republic (gérer le login `pytr` avec numéro de téléphone et PIN/Device).
    *   Récupérer l'historique des transactions.
    *   S'authentifier sur Actual Budget (URL du serveur, mot de passe, Sync ID du budget).
    *   Pousser les transactions formatées vers Actual Budget (en utilisant `actualpy` ou des requêtes HTTP).

### Étape 2 : Traitement de la Donnée (Mapping)
*   Créer une fonction qui parse le JSON renvoyé par `pytr`.
*   Filtrer les transactions annulées (ex: `"status": "CANCELED"` doivent être ignorées ou signalées visuellement).
*   Mapper les données de Trade Republic vers le format attendu par Actual Budget :
    *   `date` -> Date de la transaction (format YYYY-MM-DD).
    *   `amount.value` -> Montant (Actual Budget stocke les montants en format entier/milli-cents : multiplier par 100 et traiter les décimales selon la doc API).
    *   `title` ou `raw.title` -> Payee (Bénéficiaire).
    *   `subtitle` -> Notes/Mémo.

### Étape 3 : Création de l'Interface Utilisateur (UI)
*   Créer une page web simple avec un tableau de bord.
*   **Affichage des données :** Un tableau propre listant les transactions récupérées (Date, Bénéficiaire, Montant, Statut, Catégorie TR).
*   **Actions :**
    *   Un bouton "Connecter Trade Republic" (avec gestion de l'invite 2FA de l'app si nécessaire).
    *   Un bouton "Récupérer les transactions".
    *   Un bouton "Synchroniser avec Actual Budget".
*   Faire en sorte que l'état d'avancement et les erreurs soient visibles pour l'utilisateur (toasts ou alertes).

### Étape 4 : Dockerisation
*   Écrire un `Dockerfile` (basé sur `python:3.11-slim`).
*   Installer les dépendances via `requirements.txt` (FastAPI, uvicorn, pytr, actualpy, etc.).
*   Exposer le port de l'application (ex: 8000).
*   S'assurer que les variables d'environnement (identifiants, tokens) ne sont pas hardcodées.

### Étape 5 : Intégration Continue (GitHub Actions)
*   Créer un fichier `.github/workflows/docker-publish.yml`.
*   Le workflow doit se déclencher lors d'un `push` sur la branche `main`.
*   Il doit builder l'image Docker, se connecter au GitHub Container Registry (`ghcr.io`) via `GITHUB_TOKEN`, puis tagger et pousser l'image.

---

## 📄 Données de Référence (Payload `pytr`)

Voici la structure exacte des transactions récupérées via `pytr` que le backend devra parser :
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

Règles de parsing spécifiques :

    Ne traiter que les transactions où "status" == "EXECUTED". Ignorer "CANCELED".

    Utiliser title ou raw.title pour le nom du bénéficiaire.

    La propriété raw.eventType ou type permet de distinguer les paiements par carte (CARD_TRANSACTION) des investissements programmés (TRADING_SAVINGSPLAN_EXECUTED).

🚀 Lancement de la génération

Agent, veuillez lire ces instructions et commencer par me proposer la structure de dossiers du projet, puis implémenter l'étape 1 et 2 en premier. Demandez-moi de valider avant de passer à l'UI et au déploiement Docker.