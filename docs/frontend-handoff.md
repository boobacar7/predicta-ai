# Handoff Frontend

État de `apps/web` après la passe de l'agent Frontend. Les décisions structurantes
sont dans [ADR 0002](adr/0002-frontend-data-access.md).

## Démarrage

```bash
cd apps/web
cp .env.example .env.local
npm install
npm run dev
```

Depuis la racine : `npm run dev:web`, et `npm run verify:web` pour enchaîner
types, lint, tests et build.

## Architecture

```text
src/
├── app/                    routes App Router, chaque page délègue à une feature
├── components/
│   ├── ui/                 primitives sans logique métier
│   └── domain/             composants sportifs réutilisables
├── features/<feature>/
│   ├── <feature>-view.tsx  composition de la page
│   ├── selectors.ts        sélection et tri purs, testés
│   └── index.ts            point d'entrée public
├── data/
│   ├── mock/               fixtures fictives + scénarios + contexte scénario
│   └── http/               client fetch + HttpDataSource
├── lib/
│   ├── api/                factory, contrat public, erreurs typées
│   ├── query/              hooks TanStack Query, clés, client
│   ├── filters/            filtres utilisateur transverses
│   └── format/             formatage d'affichage
├── types/                  types API et contrat DataSource
└── test/                   helper de rendu avec providers
```

Règles appliquées :

- un composant ne fait pas d'appel réseau et ne contient pas de sélection métier;
- aucune donnée réaliste n'est écrite dans du JSX;
- les nombres circulent bruts et sont formatés à la frontière d'affichage;
- une valeur absente devient « Indisponible », jamais `0`.

## Accès aux données

```text
vue → hook (lib/query/hooks) → getDataSource(scenario) → MockDataSource | HttpDataSource
```

Le mode est résolu **par ressource**, ce qui permet de brancher l'API endpoint par
endpoint.

| Variable | Rôle |
| --- | --- |
| `NEXT_PUBLIC_PREDICTA_ENV` | Cible de déploiement. Seul `production` interdit les mocks. |
| `NEXT_PUBLIC_PREDICTA_DATA_SOURCE` | Mode par défaut : `mock` ou `http`. |
| `NEXT_PUBLIC_PREDICTA_HTTP_RESOURCES` | Ressources basculées sur l'API. |
| `NEXT_PUBLIC_PREDICTA_MOCK_RESOURCES` | Ressources maintenues sur fixtures. |
| `NEXT_PUBLIC_PREDICTA_API_BASE_URL` | Base `/api/v1`, requise dès qu'une ressource lit en HTTP. |
| `NEXT_PUBLIC_PREDICTA_REQUEST_TIMEOUT_MS` | Budget d'abandon d'une lecture. |

Exemple de bascule d'un seul endpoint :

```bash
NEXT_PUBLIC_PREDICTA_HTTP_RESOURCES=performance
NEXT_PUBLIC_PREDICTA_API_BASE_URL=http://localhost:8000/api/v1
```

La bannière passe alors en `hybrid` et l'indique explicitement.

## États d'interface

`QueryBoundary` traite loading, idle, error, empty, partial et stale pour toutes
les vues. Une vue fournit son squelette, sa définition de « vide » et, si
pertinent, un sélecteur de `DataQuality`.

Le sélecteur « Scénario mock » de la barre supérieure expose `success`, `empty`,
`partial`, `stale` et `error` sans backend. Il disparaît quand toutes les
ressources lisent en HTTP.

Le bouton « Réessayer » n'apparaît que pour une erreur réellement retentable
(`network`, `server`, `mock_scenario`). Un 404 ou une enveloppe invalide n'en
propose pas.

## Responsive

- Desktop `lg+` : sidebar persistante 256px.
- Tablette : sidebar en overlay via le bouton hamburger.
- Mobile : barre inférieure à 5 destinations, contenu dégagé par `pb-24`.

Vérifié à 1440, 820 et 390px : aucun débordement horizontal.

## Tests

`npm run test --prefix apps/web` (Vitest + Testing Library, jsdom).

Couverture actuelle : formatage et règle « jamais `0` », configuration et garde
production, client HTTP (RFC 9457, validation d'enveloppe, timeout), erreurs
typées, `MockDataSource` et ses scénarios, clés de cache, routage de la factory,
`QueryBoundary`, `StatGrid`, `MatchCard`, et `PicksView` de bout en bout.

Utiliser `renderWithProviders` de `src/test/render.tsx` pour tout composant qui
dépend des providers de l'application.

## Écarts contractuels

Résolus par [`contracts/openapi.yaml`](../contracts/openapi.yaml) :

- la route agrégée `GET /api/v1/dashboard` est canonique;
- `ModelHealthSummary.theoretical_max_drawdown` est requis et exprimé comme un
  ratio non positif;
- les listes v1 conservent `items` et `total`, avec `limit`/`offset` optionnels;
- les enveloppes, erreurs RFC 9457, filtres, enums, disponibilités et fraîcheurs
  sont définis.

`AiPick`, `AiPickExclusion`, `AiPicksMetadata`, `AiPicksResult`,
`HistoricalMatchIdentity` et les types `FootballAiAnalyst*` sont des alias de
`src/types/generated/api.ts`, régénéré par `npm run generate:api-types`
depuis `contracts/openapi.yaml`. Le reste de `api.ts` reste manuscrit
tant que la migration OpenAPI n'est pas totale.

`GET /api/v1/football/ai-analyst/{match_id}` est le contrat backend de
l'analyste football. Aucune page n'est branchée dans cette passe.

### Identité de match — consommé depuis `c31a367`

`GET /api/v1/football/ai-picks` publie `home_team`, `away_team` (nullables)
et `kickoff_at` (requis). `/ai-picks` affiche `Home vs Away`, la ligue et
le coup d'envoi. `Information indisponible` n'apparaît que lorsque le
libellé est réellement `null`.

`GET /api/v1/matches/{match_id}` peut renvoyer `MatchDetail` ou
`HistoricalMatchIdentity`. `MatchDetailView` discrimine via
`resource_scope === "structural_identity"` et n'invente ni score, ni
chronologie, ni statistiques pour un id d'archive.

Pour lire l'API réelle plutôt que les fixtures :

```
NEXT_PUBLIC_PREDICTA_HTTP_RESOURCES=football_ai_picks,matches
NEXT_PUBLIC_PREDICTA_API_BASE_URL=http://localhost:8000/api/v1
```

Le défaut reste `mock` pour le développement local sans parquet. Chaque
réponse porte encore `data_mode` ; l'UI affiche « Mock data » uniquement
lorsque l'enveloppe le dit.

### Value Finder — filtres du contrat

`GET /value` accepte `sport`, `league_id`, `date`, `status`, `limit`,
`offset`. Ceux-là partent à l'API. Marché, seuils numériques et tri n'ont
pas de paramètre équivalent : ils restent un affinage local, étiqueté
comme tel. Inventer `min_edge` sur cette route serait un contrat fantôme.

Limites restantes :

- AI Analyst : session mock déterministe, aucun appel LLM.
- Profil : placeholder, phase 10.
- Univers AI Picks V0.1 : un match candidat côté backend.

## Non fait volontairement

Backend, base de données, modèles ML, intégration provider et logique de
prédiction réelle restent hors périmètre de cet agent.
