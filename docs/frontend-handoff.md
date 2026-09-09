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

## Écarts connus à résorber

- `src/types/api.ts` est **manuscrit**. Il doit être remplacé par des types
  générés depuis `contracts/openapi.yaml`, qui n'existe pas encore. C'est l'écart
  prioritaire.
- Aucune route agrégée `GET /dashboard` n'est documentée dans AGENTS.md §16.
  `HttpDataSource` la suppose ; à confirmer avec l'agent Architecte.
- Pas de pagination curseur : `ListResult` expose `items` et `total`.
- `theoretical_max_drawdown` a été ajouté à `ModelHealthSummary` côté frontend
  pour satisfaire AGENTS.md §12. À refléter dans le contrat.
- AI Analyst : session mock déterministe, aucun appel LLM.
- Profil : placeholder, phase 10.

## Non fait volontairement

Backend, base de données, modèles ML, intégration provider et logique de
prédiction réelle restent hors périmètre de cet agent.
