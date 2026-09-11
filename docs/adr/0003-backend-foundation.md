# ADR 0003 — Fondation backend FastAPI

- Statut : accepté
- Date : 2026-09-09
- Agent : Backend
- Portée : `apps/api`, `infra/containers`, documentation associée.
  Aucune modification des vues `apps/web`.

## Contexte

Le contrat OpenAPI v1 et le prototype frontend sont stables. La phase 2 doit
exposer une API FastAPI conforme, une base PostgreSQL migrée par Alembic, et un
mode mock explicite. Il ne faut pas entraîner de modèles, ingérer de providers
ni authentifier des utilisateurs.

## Décisions

### 1. Monolithe modulaire sous `/api/v1`

Les routes délèguent à des services, qui parlent à des protocols de
repositories. SQLAlchemy reste confiné à `app/db`. Les modules métier ne
s'importent pas mutuellement via leurs tables.

### 2. Fixtures isolées, `data_mode` obligatoire

`PREDICTA_API_REPOSITORY=mock` sert des fixtures déterministes horodatées au
`PREDICTA_API_MOCK_NOW`. L'enveloppe porte toujours `data_mode: mock`.
`repository=sql` n'invente pas de matchs : les listes sont vides jusqu'à
l'ingestion. La production refuse le mock.

### 3. Value Engine déterministe, versionné

Les formules restent celles du contrat :

```text
implied_probability_raw = 1 / odds
edge = model_probability - implied_probability
expected_value = (model_probability × odds) - 1
```

Le no-vig et l'overround sont dérivés du même snapshot. `overround` est la
somme des probabilités implicites brutes (`Σ 1/odds`), pas la marge
`Σ 1/odds − 1`. La version de formule est `value-engine-0.1`, définie une
seule fois dans `app.value_engine.calculator`. Les calculs utilisent `Decimal`.

### 4. AI Analyst sans LLM

`POST /ai/analyze` construit un fact pack en liste blanche et une explication
déterministe. Aucune probabilité n'est créée par le texte. Un LLM réel est
différé (phase 6).

### 5. Santé hors contrat

`GET /health` et `GET /ready` sont opérationnels et hors OpenAPI. Ils
réutilisent l'enveloppe et `request_id` pour rester homogènes, sans étendre le
contrat public frontend.

### 6. Erreurs RFC 9457

Les erreurs GET de validation valent `400`. Le body POST invalide vaut `422`.
Le `404` est réservé aux entités inconnues. `odds`/`prediction` absents sur un
match connu restent `200` avec `data: null`.

## Conséquences

- Le frontend peut basculer endpoint par endpoint via `NEXT_PUBLIC_PREDICTA_API_BASE_URL`.
- L'agent Data pourra remplir PostgreSQL sans changer les routes.
- L'agent ML publiera des prédictions versionnées dans `predictions` /
  `model_versions`, jamais depuis l'API.
