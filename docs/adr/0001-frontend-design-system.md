# ADR 0001 — Fondation UI et design system frontend

Statut : accepté
Date : 2026-09-09
Owner : agent UI/UX

## Contexte

La phase 1 doit livrer un prototype visuel premium, contract-first, sans backend ni modèles. Le frontend doit pouvoir remplacer les mocks par HTTP sans refondre l'interface.

## Décisions

1. **Application unique `apps/web`** en Next.js App Router, TypeScript strict, Tailwind v4, Framer Motion, TanStack Query et Recharts.
2. **Design system dark SaaS** calé sur les tokens AGENTS.md (`#07090D`, `#0E1219`, `#F5F7FA`, `#8992A3`, accent violet, value vert discret).
3. **Information architecture** alignée sur la navigation cible : Dashboard, Match Center, AI Picks, Value Finder, Statistiques, Performance, Ligues, Équipes, Joueurs, AI Analyst, Profil.
4. **Couche `DataSource`** : les vues consomment des hooks TanStack Query, jamais des fixtures. Les fixtures vivent dans `src/data/mock` et portent `data_mode: mock`.
5. **Types temporaires** dans `src/types/api.ts`, snake_case, destinés à être remplacés par la génération OpenAPI.
6. **Langue d'interface : français**, y compris le formatage des probabilités (`68 %`, `+7,2 pts`).
7. **États data-driven** : loading (skeletons), error, empty, partial, stale, plus un sélecteur de scénario mock dans la barre supérieure.
8. **Pas de calcul métier de référence dans l'UI** : edge, EV et overround sont affichés tels que fournis par la datasource. Les formules restent documentées dans Value Finder.
9. **Mocks bloqués en production** sauf `NEXT_PUBLIC_PREDICTA_ALLOW_MOCK_IN_PROD=true`.
10. **Pas de logos officiels** : initiales générées, clubs et joueurs fictifs.

## Conséquences

- L'agent Frontend branche le client HTTP dans `src/data/http` et `src/lib/api/factory.ts` sans toucher aux composants de présentation.
- L'agent Architecte doit faire converger `src/types/api.ts` avec `contracts/openapi.yaml`.
- Les pages Profil, favoris et tracker restent des états « bientôt » assumés, sans écran cassé.

## Alternatives rejetées

- Apparence bookmaker / cotes en CTA.
- Données hardcodées dans le JSX.
- Store global pour probabilités et cotes.
- Visx dès le prototype (Recharts suffit).
