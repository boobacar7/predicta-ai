# PREDICTA AI — Web

Prototype Next.js du design system et de l'information architecture. Les données sont des fixtures mock clairement identifiées.

## Scripts

```bash
npm install
cp .env.example .env.local
npm run dev
npm run lint
npm run test
npm run build
```

Ouvrir [http://localhost:3000](http://localhost:3000).

## Structure

```text
src/app/                 # routes
src/components/ui/       # primitives
src/components/domain/   # composants sportifs réutilisables
src/components/layout/   # shell, nav
src/features/            # composition par écran
src/data/mock/           # fixtures data_mode=mock
src/data/http/           # stub pour l'agent Frontend
src/lib/api/             # DataSource factory
src/lib/query/           # TanStack Query
src/types/api.ts         # contrat temporaire snake_case
```

## Règles UI

Voir [docs/ui-design-system.md](../../docs/ui-design-system.md) et [docs/frontend-handoff.md](../../docs/frontend-handoff.md).
