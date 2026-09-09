# ADR 0002 — Couche d'accès aux données du frontend

- Statut : accepté
- Date : 2026-09-09
- Agent : Frontend
- Portée : `apps/web` uniquement. Aucune décision backend, data ou ML.

## Contexte

Le prototype UI livré par l'agent UI/UX couvrait déjà toutes les vues avec des
fixtures. Trois problèmes empêchaient de brancher l'API réelle sans redessiner le
frontend :

1. `createHttpDataSource()` vivait dans `src/data/mock/source.ts`. La frontière
   HTTP était donc possédée par la couche mock, et le `HttpDataSource` n'était
   qu'une série de `notImplemented`.
2. `MockScenario` était un paramètre de **chaque méthode** de `DataSource`
   (`getMatches(filters, scenario)`). Le contrat frontend divergeait donc du
   contrat OpenAPI : aucun endpoint n'accepte de « scénario ».
3. Les erreurs remontaient sous forme de `Error` brute. Les 13 vues répétaient le
   même triptyque loading/error/empty et la même chaîne
   « Réponse mock indisponible. ».

## Décisions

### 1. `DataSource` reflète le contrat, pas le mock

L'interface ne prend que les paramètres que l'endpoint correspondant accepte. Le
scénario est **lié à la construction** de la source :
`getDataSource(scenario)` renvoie une `MockDataSource` configurée. Conséquence :
`MockDataSource` et `HttpDataSource` sont strictement interchangeables, et le
jour où le mock disparaît, aucune signature d'appel ne change.

### 2. Routage par ressource, pas par application

`createDataSource()` résout le mode **ressource par ressource**
(`dashboard`, `matches`, `picks`, `value`, `performance`, `analyst`, …). La
configuration accepte `NEXT_PUBLIC_PREDICTA_HTTP_RESOURCES` et
`NEXT_PUBLIC_PREDICTA_MOCK_RESOURCES`.

Cela implémente le mode hybride prévu par architecture.md §13 : un endpoint passe
sur l'API dès qu'il existe, sans attendre les neuf autres et sans toucher aux
vues. Le `kind` résolu vaut `mock`, `http` ou `hybrid`, et la bannière affiche
l'état réel plutôt qu'une constante.

### 3. Le client HTTP est écrit maintenant, pas plus tard

`src/data/http/client.ts` est un vrai client : préfixe `/api/v1`, filtres absents
ou `"all"` non transmis, timeout borné par `AbortController`, erreurs RFC 9457
avec propagation de `request_id`.

Il **valide l'enveloppe** de réponse. Une réponse sans `data_mode` est rejetée en
`invalid_response` : c'est ce champ qui empêche qu'un payload mock soit affiché
comme donnée live pendant la migration.

### 4. Modèle d'erreur typé et transport-agnostique

`DataSourceError` porte un `kind` (`network`, `not_found`, `server`,
`invalid_response`, `not_implemented`, `mock_scenario`) et un `retryable` dérivé.

Les vues ne lisent jamais un code HTTP. Le retry automatique de TanStack Query et
le bouton « Réessayer » sont tous deux pilotés par `retryable` : un 404 ou une
violation de contrat échouerait à l'identique, donc aucune relance n'est
proposée. `mock_scenario` est retryable parce qu'il simule une panne provider et
doit donc montrer exactement l'affordance d'une vraie panne.

### 5. `QueryBoundary` centralise les états obligatoires

Un composant unique résout loading / idle / error / empty / partial / stale pour
toutes les vues (product-spec.md §10). Les vues déclarent ce que « vide » signifie
pour leur payload et fournissent leur squelette ; elles ne réimplémentent plus la
logique. Un payload dégradé reste affiché, surmonté d'un `QualityNotice` : une
réponse stale ou partielle reste une information tant que sa limite est énoncée.

### 6. `NEXT_PUBLIC_PREDICTA_ENV` distingue build et déploiement

La règle « pas de mock en production » était conditionnée à `NODE_ENV`. Or un
`next build` local vaut `NODE_ENV=production`, ce qui rendait le prototype
phase 1 **impossible à builder**. La règle porte désormais sur la cible de
déploiement déclarée, pas sur le mode de compilation.

## Conséquences

- Le passage mock → HTTP est une opération de configuration, endpoint par
  endpoint, sans refonte visuelle.
- Les composants de présentation ne contiennent plus de sélection métier : le
  filtrage et le tri vivent dans des `selectors.ts` testés par feature.
- `src/types/api.ts` reste manuscrit tant que `contracts/openapi.yaml` n'existe
  pas. C'est l'écart le plus important à résorber ; il est documenté dans
  `docs/frontend-handoff.md`.
- Ajout de Vitest et Testing Library. L'ancien runner
  (`node --experimental-strip-types` sur un fichier unique) ne pouvait pas tester
  de composant React, donc ni les états d'erreur ni les règles de disponibilité.

## Alternatives écartées

- **Garder le scénario dans la signature des méthodes** : plus simple à court
  terme, mais fige une divergence permanente avec OpenAPI.
- **Un unique interrupteur global mock/http** : oblige à migrer les dix
  ressources d'un coup, alors que le backend les livrera progressivement.
- **Attendre OpenAPI pour écrire le client HTTP** : laisse la gestion d'erreurs,
  des timeouts et de la validation d'enveloppe hors du champ de la phase 1, donc
  non testée.
