# Staging compose (Private Beta)

Smallest topology that runs the API and web **without a developer laptop layout**. Postgres stays on the compose network and is **not published** on the host. Redis is optional. `football-elo-v1-candidate` stays a **candidate**, not champion.

Laptop-only Postgres/Redis (published ports) remains [`infra/containers/docker-compose.yml`](../../infra/containers/docker-compose.yml).

## What this boots

| Service | Role |
| --- | --- |
| `postgres` | Source of truth. No host port. |
| `api` | FastAPI, `repository=sql`, `data_mode=live`, `AUTH_BYPASS` from env (default false), Alembic on start |
| `web` | Next.js standalone, `DATA_SOURCE=http` |
| `ingestion` | Optional `--profile ingest` one-shot Sportmonks/odds CLI |
| `redis` | Optional `--profile cache`. Unused by the API today. |

The API image includes `predicta_ml` / `predicta_ingestion` so it can load the frozen artefact. It does **not** train or retune Elo.

## Artefact volume

Git does not contain `artefact.joblib` or the PIT parquet. `**/var` is also dockerignored, so the API image never ships them. Staging must bind-mount real files to the paths the API already uses.

### Container contract (do not change these)

| Env | Path inside `api` |
| --- | --- |
| `PREDICTA_API_FOOTBALL_DATASET_PATH` | `/data/football/datasets/football-1x2-history.parquet` |
| `PREDICTA_API_FOOTBALL_PREMATCH_DATASET_PATH` | `/data/football/datasets/football-1x2-prematch.parquet` (optional) |
| `PREDICTA_API_FOOTBALL_REGISTRY_DIR` | `/data/football/registry` |
| model version | `football-elo-v1-candidate` (artefact at `$REGISTRY_DIR/football-elo-v1-candidate/artefact.joblib`) |

### Laptop source of truth (compose defaults)

Compose bind-mounts the gitignored worker `var/` dirs:

| Host (relative to `infra/containers/`) | Container |
| --- | --- |
| `../../workers/ingestion/var` | `/data/football/datasets` (ro) |
| `../../workers/ml/var/registry` | `/data/football/registry` (ro) |
| `../../workers/ingestion/var/raw` | `/data/football/raw` (ro on `api`) |

On a Mac that already has the frozen files:

```text
workers/ingestion/var/football-1x2-history.parquet
workers/ml/var/registry/football-elo-v1-candidate/artefact.joblib
workers/ml/var/registry/football-elo-v1-candidate/registry.json
```

those paths appear inside the API container as `/data/football/datasets/football-1x2-history.parquet` and `/data/football/registry/football-elo-v1-candidate/`. No extra copy is required.

Confirm:

```bash
docker compose -f infra/containers/compose.staging.yml \
  --env-file infra/containers/.env.staging \
  exec api ls -lh /data/football/datasets/ /data/football/registry/
```

### Isolated copy (staging VM / shared host)

When you do not want to mount the live worker tree, copy into `var/football` (still gitignored):

```bash
./infra/containers/prepare-staging-football-data.sh
```

Equivalent manual copy:

```bash
mkdir -p var/football/registry var/football/datasets var/football/raw
cp -R workers/ml/var/registry/football-elo-v1-candidate var/football/registry/
cp workers/ingestion/var/football-1x2-history.parquet var/football/datasets/
cp workers/ingestion/var/football-1x2-prematch.parquet var/football/datasets/ 2>/dev/null || true
```

Then in `.env.staging`:

```bash
PREDICTA_FOOTBALL_DATASETS_HOST=../../var/football/datasets
PREDICTA_FOOTBALL_REGISTRY_HOST=../../var/football/registry
PREDICTA_FOOTBALL_RAW_HOST=../../var/football/raw
```

Do **not** commit the parquet or joblib. Placeholder files of the same names may be used only to prove the mount; production staging must copy the real frozen artefacts. Missing files stay honest RFC 9457 `503` `/problems/model-artefact-not-found` or `422` `/problems/pit-features-unavailable`. The API does **not** fall back to mock probabilities.

Filesystem paths and `file://` URIs are accepted. `s3://` is not implemented.

## Boot

```bash
cp infra/containers/.env.staging.example infra/containers/.env.staging
# Edit CORS origin, invite allowlist, and football HOST paths if you use the isolated tree.
# Do not commit .env.staging. Do not put provider tokens in it.

# Rebuild API so the new volume contract is applied (web rebuild is optional here).
docker compose -f infra/containers/compose.staging.yml \
  --env-file infra/containers/.env.staging \
  up --build --force-recreate api
```

Full stack (API + web + unpublished Postgres):

```bash
docker compose -f infra/containers/compose.staging.yml \
  --env-file infra/containers/.env.staging \
  up --build --force-recreate
```

Open `http://localhost:3000`. The browser calls `http://localhost:8000/api/v1` (build-time `NEXT_PUBLIC_PREDICTA_WEB` / `PREDICTA_WEB_API_BASE_URL`). Rebuild `web` if that public API URL changes.

Health:

```bash
curl -sS http://localhost:8000/health
curl -sS http://localhost:8000/ready
```

`/health` reports `env=staging`, `repository=sql`, `data_mode=live`. `/docs` is off.

### Invite user

```bash
docker compose -f infra/containers/compose.staging.yml \
  --env-file infra/containers/.env.staging \
  exec -e PREDICTA_API_BOOTSTRAP_PASSWORD='...' \
  api python -m app.auth.provision beta@example.com
```

Set `PREDICTA_API_INVITE_ALLOWLIST` to that email and recreate `api` so the allowlist is picked up.

### HTTP cookies

Staging defaults `Secure` cookies. The example file sets `PREDICTA_API_COOKIE_SECURE=false` so a local HTTP compose can log in. Behind TLS, remove that override.

## Optional ingest

Postgres is not on localhost, so ingest from the compose network:

```bash
docker compose -f infra/containers/compose.staging.yml \
  --env-file infra/containers/.env.staging \
  --profile ingest run --rm \
  -e SPORTMONKS_API_TOKEN \
  -e PREDICTA_INGESTION_ENABLE_LIVE=true \
  ingestion ingest-football --league all
```

Pass the token at runtime. Do not commit it. Live ingest stays opt-in.

## Config invariants

- `PREDICTA_API_ENV=staging` + `repository=sql` + `data_mode=live`
- `AUTH_BYPASS` defaults to false. Set `PREDICTA_API_AUTH_BYPASS=true` for temporary product testing (skips login). Production still refuses bypass at boot. Rebuild `web` after changing it (`NEXT_PUBLIC_PREDICTA_AUTH_BYPASS` is inlined at build time and ignored when `NEXT_PUBLIC_PREDICTA_ENV=production`).
- Web: `NEXT_PUBLIC_PREDICTA_ENV=staging` + `NEXT_PUBLIC_PREDICTA_DATA_SOURCE=http`
- CORS origin is explicit and must include the web origin
- Candidate model version remains `football-elo-v1-candidate`

## Not in this topology

- Object store / S3 for the artefact
- CI image publish
- Redis as a cache (profile only)
- Champion promotion or Elo retune
- Auth architecture changes
