# PREDICTA AI

PREDICTA AI est une plateforme SaaS premium d'intelligence sportive. Elle transforme des données de football, basketball et tennis en statistiques, probabilités calibrées, signaux de valeur et explications traçables.

> État du projet : fondation architecturale + prototype UI mock + API FastAPI v1 (fixtures mock) + ingestion Football Sportmonks + dataset 1X2 `football-1x2-history-0.3` + premier benchmark ML Football (`workers/ml`, non branché au backend).

## Principes non négociables

- PREDICTA AI n'est pas un bookmaker.
- Une prédiction est une probabilité, jamais une garantie.
- Les probabilités proviennent de modèles statistiques ou ML versionnés.
- Le LLM explique des faits fournis et sourcés; il ne calcule pas les probabilités et n'invente aucune donnée.
- Toute donnée indisponible est signalée comme telle.
- Les mocks de développement sont identifiables et séparés des données de production.

## Architecture retenue

Le projet suivra un monorepo contract-first :

- `apps/web` : interface Next.js et couche d'accès aux données interchangeable;
- `apps/api` : API FastAPI organisée en monolithe modulaire;
- `workers/ingestion` : collecte, validation et normalisation des données sportives;
- `workers/ml` : features point-in-time, entraînement, backtesting, calibration et inférence;
- `packages/contracts` : contrats OpenAPI et schémas partagés;
- PostgreSQL : source de vérité transactionnelle;
- Redis : cache et coordination éphémère des traitements.

Les workers constituent des frontières extractibles, mais aucune architecture microservices n'est imposée prématurément.

## Documentation

- [Spécification produit](docs/product-spec.md)
- [Architecture technique](docs/architecture.md)
- [Contrat API](docs/api-contract.md)
- [Modèle de données](docs/data-model.md)
- [Conventions de développement](docs/development-conventions.md)
- [Contrat OpenAPI 3.1](contracts/openapi.yaml)
- [Instructions obligatoires des agents](AGENTS.md)
- [Design system UI](docs/ui-design-system.md)
- [Handoff agent Frontend](docs/frontend-handoff.md)
- [Handoff agent Backend](docs/backend-handoff.md)
- [Stratégie DATA](docs/data-strategy.md)
- [Fournisseurs de données](docs/data-providers.md)
- [Pipeline DATA](docs/data-pipeline.md)
- [Qualité des données](docs/data-quality.md)
- [Dataset ML football](docs/ml-dataset.md)
- [Benchmark ML football 1X2](docs/ml-football-1x2.md)
- [Validation scientifique Elo Football](docs/ml/elo-candidate-validation.md)
- [Model card Elo Football (candidate)](docs/ml/model-card-football-elo.md)
- [ADR 0001 — Fondation UI](docs/adr/0001-frontend-design-system.md)
- [ADR 0003 — Fondation backend](docs/adr/0003-backend-foundation.md)
- [ADR 0004 — Fondation DATA](docs/adr/0004-data-foundation.md)
- [ADR 0005 — Fournisseurs V1 validés](docs/adr/0005-data-providers-v1.md)

## Flux cible

```text
Sports data
  -> ingestion
  -> normalisation
  -> feature engineering
  -> modèles ML
  -> ensemble
  -> calibration
  -> probabilités
  -> Value Engine
  -> explication IA
  -> frontend
```

## Démarrage du développement

Avant tout développement parallèle :

1. initialiser Git et créer un commit de fondation;
2. faire approuver les contrats et décisions transverses;
3. attribuer un worktree et une zone d'ownership à chaque agent;
4. développer le prototype frontend contre la datasource mock conforme à OpenAPI;
5. remplacer ensuite les mocks endpoint par endpoint, sans modifier les composants de présentation.

Les commandes d'installation et d'exécution du prototype UI :

```bash
cd apps/web
cp .env.example .env.local
npm install
npm run dev
```

Depuis la racine : `npm run dev:web`.

Le prototype affiche exclusivement des fixtures fictives (`data_mode: mock`). Aucun secret ne doit être commité; les variables sont documentées dans `apps/web/.env.example`.

L'API FastAPI se lance depuis `apps/api` (voir [handoff backend](docs/backend-handoff.md)). En mode mock elle sert le même contrat OpenAPI, toujours avec `data_mode: mock`.

Staging-shaped (API + web + Postgres non publié, artefact Elo candidat en volume) : [docs/infra/staging-compose.md](docs/infra/staging-compose.md). Le candidat `football-elo-v1-candidate` n'est pas promu champion.
