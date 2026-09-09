# Handoff agent Frontend

Le prototype UI est dans `apps/web`. L'agent Frontend peut brancher l'API sans redessiner les écrans.

## Démarrage

```bash
cd apps/web
cp .env.example .env.local
npm install
npm run dev
```

Depuis la racine : `npm run dev:web`.

## Ce qui est déjà en place

- App Router, layout, navigation, design system.
- Vues : Dashboard, Match Center, détail match, AI Picks, Value Finder, Statistiques, Performance, Ligues, Équipes, Joueurs, AI Analyst, Profil.
- `DataSource` + `MockDataSource` + stub `HttpDataSource`.
- Hooks TanStack Query et query keys centralisées.
- Fixtures fictives, horloge injectée `2026-09-09T18:00:00.000Z`, `data_mode: mock`.
- Bannière mock permanente.

## Ce qu'il ne faut pas faire

- Recalculer edge / EV / overround comme source de vérité.
- Hardcoder des cotes ou stats dans un composant.
- Présenter un mock comme une donnée live.
- Inventer blessures, compos, classements réels ou performances de modèle.
- Activer le mock silencieusement en production.

## Remplacement mock → HTTP

1. Générer les types depuis `contracts/openapi.yaml` vers `src/types/generated/`.
2. Remplacer `src/types/api.ts` par des réexports générés. Conserver snake_case.
3. Implémenter `src/data/http/source.ts` avec le client généré.
4. `getDataSource()` dans `src/lib/api/factory.ts` lit déjà `NEXT_PUBLIC_PREDICTA_DATA_SOURCE`.
5. Basculer endpoint par endpoint si un mode hybride est ajouté ; chaque réponse doit exposer `data_mode`.
6. Laisser les fixtures mock pour tests et Storybook futur.

## Fichiers d'entrée

| Sujet | Chemin |
| --- | --- |
| Factory datasource | `src/lib/api/factory.ts` |
| Hooks | `src/lib/query/hooks.ts` |
| Clés | `src/lib/query/keys.ts` |
| Mock | `src/data/mock/` |
| HTTP stub | `src/data/http/source.ts` |
| Tokens | `src/app/globals.css` |
| Navigation | `src/lib/navigation.ts` |

## Écarts connus à reconcilier avec OpenAPI

- Types manuscrits dans `src/types/api.ts`.
- Pas encore de pagination curseur.
- `request_id` mock constant.
- AI Analyst : session mock déterministe, pas d'appel LLM.
- Profil : placeholder phase 10.

## Tests existants

`npm run test --prefix apps/web` couvre le formatage des probabilités (une valeur absente ne devient jamais `0`).
