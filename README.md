<div align="center">

# Lygos Python SDK

**Des appels explicites. Des erreurs lisibles. Des délais réseau configurables.**

Client Python non officiel pour créer des liens de paiement Lygos et consulter leur statut.

[![CI](https://github.com/Yusufibin/Lygos-sdk/actions/workflows/ci.yml/badge.svg)](https://github.com/Yusufibin/Lygos-sdk/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab?logo=python&logoColor=white)](pyproject.toml)
[![MIT](https://img.shields.io/badge/licence-MIT-3c9a82)](LICENSE)

[Installation](#installation) · [Utilisation](#utilisation) · [Erreurs](#erreurs) · [Documentation officielle](https://docs.lygosapp.com)

</div>

## Ce que fournit le SDK

- Création de liens via `POST /gateway` et lecture du statut via `GET /gateway/payin/{order_id}`.
- Connexion HTTP réutilisée, fermeture explicite et support du gestionnaire de contexte `with`.
- Délais de connexion et de lecture configurables, appliqués à chaque requête.
- Exceptions spécifiques pour l’authentification, les paramètres invalides, les quotas et les pannes serveur.
- Refus des réponses JSON invalides et des liens de paiement non HTTPS.
- Masquage de la clé API si elle est reflétée dans un message d’erreur du fournisseur.
- Aucun nouvel essai automatique et aucune redirection HTTP suivie par le client par défaut.

Les endpoints correspondent à la documentation Lygos : [création de gateway](https://docs.lygosapp.com/api-reference/gateway/create-payment-gateway) et [statut Payin](https://docs.lygosapp.com/api-reference/payin/get-payin-status).

## Installation

Le projet se distribue depuis les sources ; le nom d’un paquet sur PyPI n’est pas une garantie qu’il s’agit de ce dépôt.

```bash
git clone https://github.com/Yusufibin/Lygos-sdk.git
cd Lygos-sdk
python -m venv .venv
source .venv/bin/activate  # Windows : .venv\Scripts\Activate.ps1
python -m pip install .
```

## Utilisation

Placez votre clé dans la variable d’environnement `LYGOS_API_KEY` de votre application.
Le SDK ne lit ni ne crée de fichier `.env` automatiquement.

```python
import os
from lygos_sdk import LygosClient

with LygosClient(os.environ["LYGOS_API_KEY"], timeout=(5, 30)) as client:
    link = client.create_payment_link(
        amount=2500,
        shop_name="Ma boutique",
        message="Commande de démonstration",
        order_id="commande-123",
        success_url="https://example.com/success",
        failure_url="https://example.com/failure",
    )
    print(link)
```

`amount` doit être un entier strictement positif ; le SDK le transmet sans conversion de devise
ni conversion automatique d’un nombre décimal ou d’une chaîne. Les appels de l’exemple
créent une gateway sur l’environnement configuré : ils ne sont pas exécutés par les tests.

### Consulter et vérifier un statut

```python
from lygos_sdk.exceptions import LygosPaymentValidationError

with LygosClient(os.environ["LYGOS_API_KEY"]) as client:
    status = client.get_payin_status("commande-123")
    try:
        payment = client.validate_payment("commande-123")
    except LygosPaymentValidationError as error:
        print(error)
```

`validate_payment()` conserve la convention historique du SDK : seul le statut `paid`
est accepté. Un identifiant de commande non vide différent de celui demandé est rejeté.
Cette méthode ne rapproche pas les montants, les devises ou vos données de commande.
La documentation du statut expose une chaîne libre : confirmez la convention de statut
applicable à votre intégration avant d’automatiser une livraison ou une activation.
Une redirection vers `success_url` seule ne vaut pas confirmation.

### Délais et nouvelles tentatives

Le délai par défaut est `(5, 30)` secondes : connexion, puis attente de lecture.
Ce sont les délais Requests, pas une durée totale maximale de l’opération.
Un nombre simple (`timeout=15`) configure les deux délais.

Le client ne répète pas un POST échoué : un délai dépassé peut survenir après l’acceptation
de la requête par le fournisseur. Consultez l’état de la commande avant de décider
manuellement d’une nouvelle tentative. Une `Session` injectée peut avoir ses propres
politiques de retry ; sa configuration reste sous le contrôle de l’application.

### Réutiliser une session

```python
import requests

with requests.Session() as session:
    with LygosClient(os.environ["LYGOS_API_KEY"], session=session) as client:
        status = client.get_payin_status("commande-123")
```

La fermeture du client ne ferme pas une session fournie par l’application.
`base_url` peut être configurée explicitement et doit être une URL HTTPS.

## Erreurs

Toutes les exceptions du SDK héritent de `LygosError`.

| Exception | Situation |
| --- | --- |
| `LygosInvalidRequestError` | HTTP 400 ou 422 |
| `LygosAuthenticationError` | HTTP 401 ou 403 |
| `LygosNotFoundError` | HTTP 404 |
| `LygosRateLimitError` | HTTP 429 |
| `LygosServerError` | HTTP 5xx |
| `LygosNetworkError` | Erreur de transport ou délai dépassé |
| `LygosAPIError` | Réponse inattendue, JSON invalide ou autre statut HTTP |
| `LygosPaymentValidationError` | Paiement non confirmé selon la convention `paid`, ou mauvaise commande |

Les erreurs API exposent `status_code` et `response_body` lorsque disponibles.
Une erreur réseau ne permet pas de conclure qu’aucune opération n’a eu lieu.

## Développement

```bash
uv sync --extra dev
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
uv build
```

Les 44 tests utilisent un transport simulé : aucune clé réelle, aucun paiement et aucun
accès à l’API de production. La CI couvre Python 3.10 et 3.14 et construit le paquet.

## Migration 0.1 → 0.2

Les imports `lygos_sdk.client.LygosClient` et les trois méthodes existantes restent disponibles.
Python 3.10+ est maintenant requis. Les montants ne sont plus convertis silencieusement en entier,
les appels ont des délais par défaut et les redirections ne sont plus suivies automatiquement.
Les fichiers générés (`.pyc`, `.egg-info`) ont été retirés du dépôt.

## Licence

[MIT](LICENSE). Ce projet n’est pas un SDK officiel ni une certification d’intégration Lygos.
