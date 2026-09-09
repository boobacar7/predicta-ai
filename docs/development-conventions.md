# Conventions de développement

## 1. Autorité documentaire

L'ordre de priorité est :

1. règles système et demande explicite du propriétaire;
2. [`AGENTS.md`](../AGENTS.md);
3. contrat machine-readable [`contracts/openapi.yaml`](../contracts/openapi.yaml);
4. documentation de `docs/`;
5. implémentation.

Une divergence entre contrat et code bloque la fusion. Une décision transversale durable est consignée dans un ADR sous `docs/adr/`.

## 2. Principes généraux

- Petits modules avec une responsabilité claire.
- Interfaces aux frontières externes, logique métier pure au centre.
- Pas de dépendance introduite sans usage immédiat et justification.
- Pas de valeur métier magique; unités, seuils et formules sont nommés.
- Les timestamps persistés et échangés sont UTC au format RFC 3339.
- Les montants et probabilités utilisent une représentation évitant les arrondis prématurés.
- Une donnée absente est `null` avec son état de disponibilité, jamais `0` par défaut.
- Les sorties dérivées conservent provenance, version et cutoff.

## 3. TypeScript et frontend

- TypeScript strict; `any` est interdit sauf frontière non typable documentée.
- Types API générés depuis OpenAPI; ne pas les éditer manuellement.
- Composants fonctionnels, petits et composables.
- État serveur avec TanStack Query; état local au plus près du composant.
- Pas de requête réseau directe dans un composant de présentation.
- Pas de données réalistes hardcodées dans le JSX.
- Les exports publics d'une feature passent par un point d'entrée explicite.
- Les nombres sont conservés bruts et formatés à la frontière d'affichage.
- Les couleurs seules ne transmettent jamais un état.
- Les animations respectent `prefers-reduced-motion`.

Conventions de nommage :

- composants et types : `PascalCase`;
- fonctions, hooks et variables : `camelCase`;
- hooks : préfixe `use`;
- fichiers de composants : convention unique choisie au scaffold et appliquée par lint;
- query keys : factory centralisée, stable et sérialisable.

## 4. Python et backend/data/ML

- Version Python commune fixée au scaffold.
- Typage complet des interfaces publiques; `mypy` ou `pyright` configuré en mode strict pragmatique.
- Formatage et lint avec Ruff.
- Pydantic aux entrées/sorties; modèles SQLAlchemy confinés à la persistance.
- `Decimal` pour les formules de cotes/value lorsque la reproductibilité l'exige.
- Pas de requête SQL ou d'appel provider dans une route FastAPI.
- Sessions DB et transactions explicites.
- Fonctions de features sans accès implicite à l'avenir.
- Seeds, versions et paramètres enregistrés pour toute expérience ML.
- Notebooks réservés à l'exploration; la logique validée migre vers des modules testés.

## 5. API

- Préfixe public `/api/v1`.
- Noms de ressources au pluriel.
- JSON en `snake_case` pour rester cohérent avec Pydantic et OpenAPI.
- Pagination par curseur pour les historiques volumineux; pagination simple tolérée seulement pour catalogues bornés.
- Erreurs au format Problem Details RFC 9457.
- `request_id` propagé et retourné sur erreur.
- Ajouts compatibles autorisés dans v1; suppression, renommage ou changement sémantique exigent dépréciation ou v2.
- Toute route précise auth, cache, erreurs, disponibilité et provenance attendues.

## 6. Données et migrations

- PostgreSQL est la source de vérité; Redis et index dérivés sont reconstruisibles.
- Alembic est l'unique mécanisme de migration.
- Une seule branche possède une nouvelle révision Alembic à la fois.
- Migrations rétrocompatibles selon expand/migrate/contract.
- Aucun payload provider brut n'est perdu lors de la normalisation.
- Les corrections sont traçables et rejouables.
- Les tables de faits volumineuses sont append-only autant que possible.
- Les suppressions de données utilisateur suivent une politique documentée.

## 7. ML et probabilités

- Split temporel obligatoire pour les mesures de référence.
- Features calculées avec un cutoff explicite.
- Calibration entraînée hors du jeu de test.
- Promotion conditionnée par log loss, Brier, calibration et stabilité, pas seulement accuracy.
- Toute prédiction publiée référence modèle, calibrateur, features et cutoff.
- Une modification de formule du Value Engine incrémente sa version.
- ROI et drawdown sont qualifiés de théoriques lorsqu'ils proviennent d'un backtest.

## 8. Mocks

- Fixtures dans `apps/web/src/data/mock`.
- Toutes portent `data_mode: mock`.
- Même schéma que les réponses API.
- Dates relatives générées à partir d'une horloge injectée pour rendre les tests déterministes.
- Scénarios nommés : success, empty, partial, stale et error.
- Les mocks ne sont jamais activés silencieusement en production.

## 9. Configuration et secrets

- Variables documentées dans `.env.example` au moment où elles deviennent nécessaires.
- Aucun secret, token, mot de passe ou credential dans Git, logs, fixtures ou captures.
- Configuration validée au démarrage avec échec explicite.
- Noms préfixés par application lorsque nécessaire, par exemple `PREDICTA_API_`.
- Valeurs de développement non sensibles seulement dans les fichiers versionnés.

## 10. Tests et qualité

### Pyramide

- unités : règles métier, formules, transformations et composants;
- contrats : validation OpenAPI des producteurs et consommateurs;
- intégration : PostgreSQL, Redis et adaptateurs;
- data/ML : qualité, idempotence, anti-leakage, calibration et reproductibilité;
- E2E : parcours critiques uniquement;
- accessibilité : automatisée puis contrôle manuel ciblé.

### Exigences de PR

- lint et types passent;
- tests pertinents ajoutés ou justification;
- contrat et docs mis à jour si comportement public changé;
- états loading/error/empty/partial couverts pour les vues data-driven;
- pas de secret ni de donnée sportive présentée comme réelle;
- changement limité à l'ownership annoncé;
- migration et rollback documentés si applicable.

La couverture est un signal, pas une fin. Les règles de probabilité, value, cutoff temporel et disponibilité demandent des tests de propriétés et de limites.

## 11. Commits, branches et revues

- Branche : `agent/<role>/<feature>`.
- Une branche correspond à un sujet reviewable.
- Commits atomiques, message à l'impératif et sans fichiers sans rapport.
- Rebase/synchronisation avant transfert, sans réécrire le travail partagé.
- Une modification de `contracts/openapi.yaml`, migrations, dépendances racine ou CI demande la revue de l'owner.
- Ne jamais supprimer ou écraser du travail existant pour résoudre un conflit.

## 12. Definition of Done

Une livraison est terminée lorsque :

- le comportement demandé fonctionne;
- types, lint et tests passent;
- erreurs et données partielles sont gérées;
- responsive et accessibilité sont considérés;
- observabilité utile existe;
- sécurité et secrets sont vérifiés;
- documentation et contrats sont cohérents;
- aucun chiffre inventé n'est présenté comme réel;
- les limites et arbitrages restants sont explicités.
