# OOS historical odds expansion

**Branch:** `agent/data/expand-oos-historical-odds`  
**Nature:** data collection only. No model, calibration, Elo K, home advantage, Value Engine, AI Picks threshold, ranking, PIT, or OOS evaluator change.  
**CLI:** `python -m predicta_ingestion expand-oos-historical-odds`  
**Estimate (0 credits):** `--estimate-only`  
**Artefacts:**

- `workers/ml/reports/oos-odds-coverage.json`
- `workers/ml/reports/oos-odds-expansion-manifest.json`

**Model:** `football-elo-v1-candidate` — not promoted, not retrained.  
**OOS protocol:** `docs/ml/production-oos-protocol.md` — not modified.  
**Production OOS backtest:** **not rerun** in this task.

This report measures **matches with valid live PIT 1X2 odds**. It does **not** count AI Picks, hit rate, or ROI. Those numbers exist only after the frozen `production-oos-backtest` is rerun on the expanded snapshots.

The previous OOS conclusion remains:

**`INSUFFICIENT OOS EVIDENCE`**

until that backtest is rerun.

The Odds API key is read from `workers/ingestion/.env` (gitignored). It does not appear in logs, fixtures, reports, tests, or Git.

---

## 1. Objective

Increase historical 1X2 coverage for the already-validated true OOS window, using the existing The Odds API v4 provider and persist architecture.

Target:

```text
dataset 0.3 final_test
event_at >= 2026-07-01T00:00:00Z
event_at <  2026-09-10T02:30:01Z
status = finished
sport  = football
```

Universe size is frozen at **387** matches. This task does not add matches, invent odds, or change identity resolution.

---

## 2. OOS period

Copied from the frozen protocol. Not reinvented.

| Bound | UTC |
| --- | --- |
| Freeze / start (inclusive) | `2026-07-01T00:00:00Z` |
| End (exclusive) | `2026-09-10T02:30:01Z` |
| First OOS kickoff in parquet | `2026-07-07T16:00:00Z` |
| Last OOS kickoff in parquet | `2026-09-10T02:30:00Z` |

Cutoff policy (unchanged):

```text
cutoff_at == kickoff_at == event_at
odds.available_at <= cutoff_at
odds.available_at <= kickoff_at
selected snapshot = last complete 1X2 ordered by (available_at, collected_at, snapshot.id)
```

No 2024 collection. No May/June 2026 collection. No post-kickoff snapshots.

---

## 3. Existing coverage

Three baselines are recorded so this report does not rewrite history.

| Baseline | Matches with valid live PIT 1X2 | Coverage |
| --- | ---: | ---: |
| Frozen production OOS backtest (`docs/ml/production-oos-backtest.md`) | **53 / 387** | **13.7%** |
| Independent SQL audit at the start of this task | **54 / 387** | **13.95%** |
| Execute-time SQL baseline used by this runner | **76 / 387** | **19.64%** |

The 53-match figure is what the current `production-oos` command reads from `workers/ingestion/var/persisted-final-test-history-score.json` (Premier League + Ligue 1 analytical quotes). SQL already held a few additional live snapshots for La Liga, Bundesliga, and Champions League when this runner executed; those 76 are the honest before-count for **this** ingestion.

This runner’s newly covered matches: **38**.

SQL coverage after this runner: **114 / 387 = 29.46%**.

---

## 4. Target competitions

Existing seven V1 football competitions only. Existing sport keys only.

| Competition | OOS matches | Odds API sport key |
| --- | ---: | --- |
| Premier League | 30 | `soccer_epl` |
| Ligue 1 | 27 | `soccer_france_ligue_one` |
| La Liga | 41 | `soccer_spain_la_liga` |
| Bundesliga | 18 | `soccer_germany_bundesliga` |
| Serie A | 30 | `soccer_italy_serie_a` |
| Champions League | 102 | `soccer_uefa_champs_league` |
| MLS | 139 | `soccer_usa_mls` |

Market: `h2h` → canonical `1X2` (`HOME` / `DRAW` / `AWAY`).  
Region: `eu`.  
Provider: The Odds API v4 historical endpoint already implemented in `workers/ingestion/`.

No extra bookmakers, markets, or sport keys.

---

## 5. Request strategy

Reuse `persist_historical_odds.py` cadence. Do **not** request one snapshot per match.

```text
1 historical request / competition / UTC kickoff day
as_of = earliest kickoff that day
MIN_SLOT_GAP = 12h
```

`as_of` is the earliest kickoff so the provider’s closest snapshot is `<=` kickoff. Adjacent MLS slots across UTC midnight that fall inside 12h keep the **earlier** timestamp (the later one would be post-kickoff for the previous match).

Skipped before any live call:

- league-days whose historical `request_key` is already persisted
- league-days whose target matches already have a valid pre-kickoff live 1X2 snapshot
- isolated Paris FC matches (`tm_football-sportmonks-4508`)
- dates outside `2026-07-01` → `2026-09-10`
- 2024 and May/June 2026 windows

`--estimate-only` plans slots from parquet + PostgreSQL and reads quota via `GET /v4/sports` (documented 0 credits). It does not call `/v4/historical/...`.

Execute-time plan:

| Item | Count |
| --- | ---: |
| Planned league-days in the OOS window | 101 |
| Already requested (skipped) | 38 |
| Already persisted (skipped) | 2 |
| MLS coalesced | 10 |
| Fetch slots this run | **51** |
| Plan SHA-256 | `070efaaef94b3e6527f5b304fc1331e7217562dd8aded9150fedeeb45d343dcd` |

Fetched leagues this run: Champions League (14), La Liga (11), MLS (15), Serie A (11). Premier League, Ligue 1, and Bundesliga league-days were already in `raw_payloads.request_key`.

---

## 6. Planned credit consumption

Documented cost: **10 credits** per historical request (`CREDITS_PER_HISTORICAL_REQUEST_DOCUMENTED`).

| Plan | Requests | Credits |
| --- | ---: | ---: |
| First dry-run (before execute-time skip of already-requested keys) | 70 | 700 |
| Execute-time estimate (`--estimate-only` equivalent inside the live run) | **51** | **510** |
| Cap | 85 | 850 |

Quota remaining before historical spend (header): **18,010**. 510 credits is 2.8% of remaining quota and is justified by 38 additional identity-matched OOS matches plus reusable raw snapshots. The run was not stopped.

---

## 7. Actual credit consumption

| Meter | Before | After | Delta |
| --- | ---: | ---: | ---: |
| Sum of `x-requests-last` (this runner) | — | — | **510** |
| `x-requests-remaining` header | 18,010 | 17,120 | 890 |

The header remaining delta (890) and the sum of `x-requests-last` (510) disagree, as on prior Odds API runs. This report treats **510** as the credits consumed by the 51 historical requests. The remaining header after the run is **17,120**.

Rejected requests: **0**.  
`stop_reason`: none.

---

## 8. Number of requests

**51** successful historical requests. **0** rejected.

Breakdown by competition (this run):

| Competition | Requests |
| --- | ---: |
| Champions League | 14 |
| MLS | 15 |
| La Liga | 11 |
| Serie A | 11 |
| Premier League | 0 (reused) |
| Ligue 1 | 0 (reused) |
| Bundesliga | 0 (already requested) |

---

## 9. Number of snapshots

PostgreSQL counts from the frozen manifest:

| Table | Before | After | Delta |
| --- | ---: | ---: | ---: |
| `matches` | 7,622 | 7,622 | **0** |
| `odds_snapshots` (all live) | 34,190 | 37,795 | **+3,605** |
| `odds_snapshots` (`data_mode=mock`) | 0 | 0 | 0 |
| `odds_selections` | 102,570 | 113,385 | +10,815 |
| `odds_raw_payloads` | 154 | 193 | +39 |
| `odds_ingestion_runs` | 4 | 6 | +2 |

Pipeline persist stats for the 51 fetches: **1,835** snapshot records accepted, **31** idempotent duplicates. Odds events never created matches. Duplicate snapshot IDs after ingest: **0**. Post-kickoff live snapshots on the 387 OOS matches: **0**.

---

## 10. Number of newly covered matches

**38** matches gained a valid live pre-kickoff 1X2 snapshot during this run.

Relative to the frozen OOS backtest (53) the SQL PIT set is now 114, a **+61** match increase in persisted PostgreSQL coverage. The 23-match gap between the backtest artefact (53) and this runner’s execute baseline (76) is pre-existing SQL, not this fetch.

---

## 11. Coverage before

| Source | Covered | Coverage |
| --- | ---: | ---: |
| Production OOS backtest artefact | 53 / 387 | 13.7% |
| This runner execute baseline | 76 / 387 | 19.64% |

---

## 12. Coverage after

**114 / 387 = 29.46%** valid live PIT 1X2 snapshots.

Still uncovered: **273**.

This is **matches with odds**, not AI Picks. AI Picks eligibility requires the frozen Value Engine and `ai-picks-0.1` exclusions and can only be counted by rerunning `production-oos-backtest`.

All 114 covered snapshots have `latest_odds_available_at <= kickoff` and snapshot age in **264 s … 81,278 s** (max ≈ 22.6 h), which is below the published 24 h stale-odds threshold. That does **not** imply they will become AI Picks.

---

## 13. Coverage by competition

| Competition | Matches | Before (execute) | After | Newly covered this run | Still uncovered |
| --- | ---: | ---: | ---: | ---: | ---: |
| Premier League | 30 | 30 | 30 | 0 | 0 |
| Ligue 1 | 27 | 24 | 24 | 0 | 3 |
| La Liga | 41 | 9 | 12 | 3 | 29 |
| Bundesliga | 18 | 7 | 7 | 0 | 11 |
| Serie A | 30 | 0 | 22 | 22 | 8 |
| Champions League | 102 | 6 | 6 | 0 | 96 |
| MLS | 139 | 0 | 13 | 13 | 126 |
| **Total** | **387** | **76** | **114** | **38** | **273** |

---

## 14. Rejected events

In-window Odds API events observed this run: **198**.

| Identity outcome | Count |
| --- | ---: |
| Exact natural-key matches | 43 |
| Alias matches | 0 |
| Rejected / unmatched | 150 |
| `false_match_count` | **0** |

Provider quarantine (unique event ids recorded in the coverage artefact): **192**, all `unmatched_odds_event`. Unmatched events never created or attached to Sportmonks matches.

OOS matches still without a valid snapshot: **273**, recorded in `oos-odds-coverage.json` (`rejected_events`). None were silently dropped.

---

## 15. Rejection reasons

Match-level (coverage matrix):

| `rejection_reason` | Matches |
| --- | ---: |
| _(none — valid pre-match snapshot)_ | 114 |
| `no_live_1x2_snapshot` | 270 |
| `isolated_team: Paris / Paris FC / PSG kept distinct` | 3 |

The 270 `no_live_1x2_snapshot` rows are identity misses or competition-key misses, not discarded payloads. Typical unmatched Odds API names (not aliased, not guessed):

- `CA Osasuna`, `Celta Vigo`, `Elche CF`, `Deportivo La Coruna`, `Alaves`, `Real Racing Club de Santander`, `Malaga`
- `Inter Milan`, `AS Roma`, `Atalanta BC`
- `Bayern Munich` vs Sportmonks `Bayern München`
- MLS franchise suffixes (`Toronto FC` vs `Toronto`, `CF Montréal`, …)
- Champions League **qualifying** clubs (Lincoln Red Imps, Ararat-Armenia, …) which are not on `soccer_uefa_champs_league`

Identity resolution was **not** expanded. Uncertain events stay quarantined.

Isolated Paris FC (Sportmonks `tm_football-sportmonks-4508`), uncovered by design:

- Troyes vs Paris (`mth_football-sportmonks-19715629`)
- Paris vs Nice (`mth_football-sportmonks-19715623`)
- Olympique Marseille vs Paris (`mth_football-sportmonks-19715615`)

Pre-existing documented listing `mth_football-sportmonks-19715631` (Rennes vs Paris Saint Germain, `inverted_home_away: PSG/Rennes vs Rennes/PSG`) already has valid PIT odds from earlier PL/Ligue 1 persist. This run did not refetch Ligue 1 and did not invert HOME/AWAY. It is counted in the runner’s `isolated_matches=4` accounting because it sits in `KNOWN_IDENTITY_EXCLUSIONS`, but it is **covered**.

---

## 16. PIT validation

Read-only checks against the frozen protocol. Evaluator not modified.

| Check | Result |
| --- | --- |
| `available_at <= kickoff_at` for all 114 covered matches | pass |
| `available_at` after cutoff / post-kickoff on OOS matches | **0** |
| Negative snapshot age | **0** |
| Any covered `available_at` before `2026-07-01T00:00:00Z` | **0** |
| Pipeline `pit_check` on a fetched match | `passed=true`, `leaked=false` |
| Sample | `mth_football-sportmonks-19609610`, cutoff `2026-07-18T02:25:00Z`, selected `2026-07-18T00:05:34Z` |

Bookmaker `last_update` fields inside a historical payload may predate July (provider metadata). Snapshot `available_at` used for PIT is the historical request timestamp, and every covered OOS snapshot is inside the OOS window and strictly before or at kickoff.

---

## 17. Identity validation

Existing resolver only: exact `football|home|away|kickoff` plus already registered `TEAM_ALIASES`. No new aliases. No HOME/AWAY inversion. No fuzzy match.

| Check | Result |
| --- | --- |
| Paris FC / Paris / PSG isolation | preserved; 3 Paris FC matches remain uncovered |
| Reims aliases | unchanged |
| False matches | **0** |
| Odds-created matches | **0** (`matches` stayed 7,622) |
| Canonical match IDs | unchanged |

Remaining gaps are name/key mismatches and Champions League qualifying (different Odds API sport key, not in V1 mapping). Those are reported, not guessed.

---

## 18. Mock / live isolation

| Check | Result |
| --- | --- |
| New snapshots `data_mode` | `live` |
| `odds_snapshots` with `data_mode=mock` | **0** before and after |
| Parquet OOS rows `data_mode` | `live` (runner refuses otherwise) |
| Mock odds used to inflate coverage | no |

---

## 19. Idempotence

| Check | Result |
| --- | --- |
| Duplicate snapshot IDs | 0 |
| Persist duplicate records this run | 31 (same snapshot written twice → keep first) |
| Repeated raw checksum | same `raw_payload_id` reused (e.g. empty/identical CL historical bodies) |
| Overwrite of historical snapshots | no |
| Re-request of existing `request_key`s | skipped |

A second execution of `expand-oos-historical-odds --estimate-only` after this run plans **0** additional fetches for already covered/requested slots.

---

## 20. Reproducibility

Frozen manifest: `workers/ml/reports/oos-odds-expansion-manifest.json`.

| Field | Value |
| --- | --- |
| `oos_start` | `2026-07-01T00:00:00Z` |
| `oos_end` | `2026-09-10T02:30:01Z` |
| `provider` | `the_odds_api` |
| `market` | `h2h` |
| `region` | `eu` |
| `plan_sha256` | `070efaaef94b3e6527f5b304fc1331e7217562dd8aded9150fedeeb45d343dcd` |
| Requested timestamps | 51 (listed in the manifest) |
| Successful requests | 51 |
| Rejected requests | 0 |
| Credits before / after (headers) | 18,010 / 17,120 |
| Additional credits consumed | 510 |
| Snapshots added | 3,605 |
| Snapshots reused (matches already covered at execute) | 76 |
| Matches newly covered | 38 |
| Matches still uncovered | 273 |

CLI: `python -m predicta_ingestion expand-oos-historical-odds`. Raw payloads remain under gitignored `workers/ingestion/var/raw/`.

---

## 21. Remaining gaps

273 / 387 OOS matches still lack a valid live PIT 1X2 snapshot.

Largest holes:

1. **Champions League qualifying (96 uncovered)** — historical `soccer_uefa_champs_league` does not list most July–August qualifying fixtures. Adding `soccer_uefa_champs_league_qualification` would be a new sport key and is out of scope.
2. **MLS name suffixes (126 uncovered)** — Odds API franchise names often differ from Sportmonks names. Existing MLS franchise aliases are **not** applied to odds natural keys. Not guessed here.
3. **La Liga / Bundesliga / remaining Serie A prefixes** — `CA Osasuna`, `Bayern Munich` / `Bayern München`, `Inter Milan` / `Inter`, etc.
4. **Paris FC isolation (3 matches)** — by design.

Further coverage without new aliases yields little: the remaining league-days are already requested or the events are unmatched. The credit-efficient next step is a **separate, explicit identity-alias review** (not this task), then re-ingest already stored raw payloads (0 new credits).

---

## 22. Recommendation for rerunning OOS backtest

**Yes — it is now appropriate for the next task to rerun the frozen `production-oos-backtest`.**

Conditions:

- Do **not** change the protocol, model, thresholds, Value Engine, or PIT.
- Do **not** spend Odds API credits.
- Attach **PostgreSQL live PIT snapshots** for the 387 OOS match IDs (`SqlOddsRepository`, `data_mode=live`), the same pattern as `persisted-expanded` / `persisted-final-test-history`.
- The current `production-oos` command still reads `persisted-final-test-history-score.json` (~53 PL + Ligue 1 quotes). Rerunning it unchanged would **ignore** the new Serie A / MLS / La Liga snapshots.
- Report **matches with odds** separately from **AI Picks**. Do not treat 114 as an AI Picks count.
- Keep the verdict **`INSUFFICIENT OOS EVIDENCE`** unless the frozen sufficiency rules (coverage, pick count) are actually met after that run.

This collection improved SQL PIT coverage from 13.7% (backtest artefact) / 19.6% (execute baseline) to **29.5%**. That is material and still below the protocol’s 50% coverage bar.

---

## Quality gates

Equivalent `npm run verify:all` (each package `.venv`): **PASS**. OpenAPI unchanged. No secrets in artefacts.

| Gate | Result |
| --- | --- |
| `verify:api` | ruff + mypy + **596 passed** |
| `verify:ingestion` | ruff + mypy + **192 passed**, 1 skipped |
| `verify:ml` | ruff + mypy + **46 passed** (includes frozen OOS tests; evaluator untouched) |
| `verify:web` | OpenAPI types unchanged + typecheck + lint + **283 passed** + Next.js build |

Targeted ingestion coverage for this change: `test_oos_historical_odds.py` (15), persist/expand/historical Odds API pilots, identity, `test_the_odds_api.py`.

`production-oos-backtest` was **not** rerun. No ROI or hit-rate figure is reported.
