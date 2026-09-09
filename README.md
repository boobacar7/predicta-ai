# PREDICTA AI

PREDICTA AI est une plateforme SaaS premium d'intelligence sportive. Elle transforme des données de football, basketball et tennis en statistiques, probabilités calibrées, signaux de valeur et explications traçables.

> État du projet : fondation architecturale. Le frontend, le backend, les pipelines data et les modèles ML ne sont pas encore implémentés.

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
- [Roadmap](docs/development-roadmap.md)
- [Contrat OpenAPI 3.1](contracts/openapi.yaml)
- [Instructions obligatoires des agents](AGENTS.md)

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

Les commandes d'installation et d'exécution seront ajoutées avec les premiers scaffolds applicatifs. Aucun secret ne doit être commité; les futures variables requises seront documentées dans `.env.example`.
