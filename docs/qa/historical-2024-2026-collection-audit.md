# Historical 2024–2026 Odds collection — cost / coverage audit

**Decision: STOP**

Stopped because 711 remaining claimed requests are expected to add approximately
0 additional canonical OOS matches at a cost of 7110 credits.

Audited at 2026-09-12T15:12Z. Data collection only. No backtest, no ROI, nothing
deleted, no rollback.

Machine-readable copy: `workers/ml/reports/historical-2024-2026-collection-audit.json`.

---

## Live probe (this environment)

There is **no running 2024–2026 collection job** in this Cloud Agent VM.

| Check | Result |
| --- | --- |
| Collector / ingestion process | none (only mock `uvicorn` + `next dev`) |
| PostgreSQL `:5432` | closed |
| Docker Compose Postgres | not running |
| `THE_ODDS_API_KEY` | absent — live `x-requests-*` headers cannot be read |
| `workers/ingestion/var` raw store | absent |
| Accessible cloud agents running a collector | 0 |
| 1348-request planner on `main` | absent (collector lives on unmerged data branches) |

The numbers `637 / 1348`, `436` new requests, `~19 s/request`, `~4.8 h remaining`,
`637` raw keys, and `~1114` PIT records were supplied in the audit prompt. They
are **not** present in any process, database, raw store, or git artefact reachable
from this environment. They are treated as unverified claims.

This environment cannot stop a collector on another machine. It also must not
start a new 1348-request historical spend.

---

## 1. Credit audit

Live Odds API quota in this VM:

| Field | Value |
| --- | --- |
| `credits_before` | **unavailable** |
| `credits_consumed` | **unavailable** |
| `credits_remaining` | **unavailable** |
| `estimated_remaining_cost` | **unavailable** |
| `estimated_final_cost` | **unavailable** |

Reason: no API key, so `GET /v4/sports` (documented 0 credits) cannot be used to
read `x-requests-remaining` / `x-requests-used` / `x-requests-last`.

### Last verified headers (actual Odds API metadata)

Source: `persist.fetches[].quota` in
`workers/ml/reports/oos-odds-final-batch.json` on
`origin/agent/data/final-oos-odds-batch` (`1cde8f7`, 2026-09-12 11:38:38 +0200).

Probe remaining came from `GET /v4/sports`. Each historical call billed
`x-requests-last = 10`.

| Field | Value |
| --- | --- |
| `credits_before` | **17110** (`x-requests-remaining` after sports catalog probe) |
| `credits_consumed` | **100** (`sum(x-requests-last)` over 10 historical requests) |
| `credits_remaining` | **17010** (last historical response) |
| `estimated_remaining_cost` | **0** (that job completed) |
| `estimated_final_cost` | **100** |

| `as_of` | sport | `x-requests-last` | `x-requests-used` | `x-requests-remaining` |
| --- | --- | ---: | ---: | ---: |
| 2026-07-17T00:30:00Z | `soccer_usa_mls` | 10 | 2900 | 17100 |
| 2026-07-23T00:15:00Z | `soccer_usa_mls` | 10 | 2910 | 17090 |
| 2026-07-26T00:30:00Z | `soccer_usa_mls` | 10 | 2920 | 17080 |
| 2026-08-02T00:10:00Z | `soccer_usa_mls` | 10 | 2930 | 17070 |
| 2026-08-16T00:30:00Z | `soccer_usa_mls` | 10 | 2940 | 17060 |
| 2026-08-20T00:00:00Z | `soccer_usa_mls` | 10 | 2950 | 17050 |
| 2026-08-23T00:30:00Z | `soccer_usa_mls` | 10 | 2960 | 17040 |
| 2026-08-30T00:30:00Z | `soccer_usa_mls` | 10 | 2970 | 17030 |
| 2026-09-06T00:30:00Z | `soccer_usa_mls` | 10 | 2980 | 17020 |
| 2026-09-10T00:00:00Z | `soccer_usa_mls` | 10 | 2990 | 17010 |

Documented historical cost remains **10 credits / request**.

### If the unverified 1348-request job were real

This row is **not** measured. It only applies 10 credits per claimed new request
to the last verified remaining balance.

| Field | Hypothetical |
| --- | ---: |
| `credits_before` | 17010 |
| `credits_consumed` | 4360 (436 × 10) |
| `credits_remaining` | 12650 |
| `estimated_remaining_cost` | 7110 (711 × 10) |
| `estimated_final_cost` | 11470 |

Do not treat this block as Odds API metadata.

---

## 2. Coverage audit

Live PostgreSQL coverage by year **cannot be computed**. Port 5432 is closed.
Inventing 2024 / 2025 / 2026 percentages would violate data integrity rules.

Coverage below is the last verified SQL snapshot. It counts **canonical matches
with a valid pre-kickoff 1X2 snapshot**. It does not count raw events as matches
and does not count snapshot rows as matches.

Universe: dataset 0.3 true OOS window only
(`2026-07-01T00:00:00Z` inclusive → `2026-09-10T02:30:01Z` exclusive).
**387** target matches.

| Competition | Target matches | Matches with valid PIT odds | Coverage % |
| --- | ---: | ---: | ---: |
| Premier League | 30 | 30 | 100.00 |
| Ligue 1 | 27 | 24 | 88.89 |
| La Liga | 41 | 12 | 29.27 |
| Bundesliga | 18 | 7 | 38.89 |
| Serie A | 30 | 22 | 73.33 |
| Champions League | 102 | 6 | 5.88 |
| MLS | 139 | 80 | 57.55 |
| **Total (OOS window)** | **387** | **181** | **46.77** |

| Year | Target matches | Matches with valid PIT odds | Coverage % |
| --- | --- | --- | --- |
| 2024 | unavailable | unavailable | unavailable |
| 2025 | unavailable | unavailable | unavailable |
| 2026 (OOS window only) | 387 | 181 | 46.77 |
| 2026 outside OOS / full calendar | unavailable | unavailable | unavailable |

SQL inventory at that snapshot (not match coverage):

- canonical matches: 7622
- live odds snapshots: 43280
- odds raw payloads: 203
- mock snapshots: 0

User-claimed PIT coverage `~1114 records` is **not verified**. 43280 is a
snapshot count, not a match count. Valid PIT match coverage is **181 / 387** in
the OOS window.

Ligue 1 includes 3 isolated Paris FC matches that must not be aliased.

---

## 3. Marginal value of remaining requests

Last completed paid job (`expand-oos-final-odds-batch`):

| Item | Count |
| --- | ---: |
| Planned requests | 25 |
| Executed (paid) | 10 |
| Skipped (wrong sport key) | 15 |
| Reused existing request keys | 77 |
| Credits consumed | 100 |
| New canonical OOS matches from those 10 paid requests | **0** |
| New canonical OOS matches from 0-credit MLS raw replay | **67** |
| New fetch events | 141 |
| Exact identity matches | 80 |
| Unmatched (fetch events + replay quarantines) | 3738 |
| False matches | 0 |

Premier League, Ligue 1, La Liga, Bundesliga, Serie A, and Champions League
coverage **did not move** after the 10 paid MLS historical calls. All +67 OOS
matches were MLS franchise-alias replay of payloads already stored.

Remaining paid work is blocked by identity / catalog, not by missing timestamps:

- Champions League qualifying clubs (Lincoln Red Imps, Inter Club d'Escaldes,
  The New Saints, Sabah, …) have no Odds API sport key
  (`soccer_uefa_champs_league_qualification` absent from `/v4/sports`).
- La Liga, Bundesliga, remaining MLS suffixes, and CL group-stage names stay
  quarantined. Names are not guessed.
- Target matches that already have a valid pre-kickoff 1X2 snapshot are skipped
  by the persist planner; refetching those days does not add canonical matches.

Taking the unverified 1348-request claim at face value:

| Item | Value |
| --- | ---: |
| Requests remaining | 711 |
| Requests already in the 637 (reused vs new) | 201 reused / 436 new |
| Expected new canonical OOS matches | **~0** if remaining slots resemble the last paid batch |
| Expected final OOS coverage if stopped now | **181 / 387 (46.77%)** |
| Marginal canonical OOS matches per 100 credits (last paid batch) | **0** |

Further historical requests would still increase **raw snapshots**. That is not
the optimisation target. The target is additional valid canonical matches with
PIT odds.

---

## 4. Stop condition

Remaining requests have poor expected marginal value.

- No live job exists here to continue.
- The last 100 paid credits added 0 canonical OOS matches.
- 15 planned CL-qualification slots cannot map to Sportmonks via The Odds API.
- Completing 711 claimed remaining requests would cost **7110 credits**.

Do not continue blindly. Do not start a replacement 1348-request spend from this
VM.

---

## 5. What was preserved

- No raw payloads deleted
- No snapshots deleted
- No ingestion metadata deleted
- No rollback
- Idempotence unchanged
- `production-oos-backtest` not run
- `final-oos-evaluation` not run
- ROI not calculated

---

## 6. Decision

**B. STOP**

Stopped because 711 remaining claimed requests are expected to add approximately
0 additional canonical OOS matches at a cost of 7110 credits.

Resume only after:

1. The collector VM (with Postgres + Odds API key) is identified, **or**
2. Identity matching is fixed for unmatched Odds API names / CL qualification,
   **and**
3. A remaining-slot plan shows expected new canonical matches, not raw snapshot
   growth.

Until then, keep the persisted OOS snapshots (181/387) and the last verified
quota remaining of **17010**.
