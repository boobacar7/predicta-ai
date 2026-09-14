# Walk-forward 2024–2026 protocol freeze

**Protocol id:** `walk-forward-2024-2026-v1`
**Kind:** audit + protocol freeze. Not a backtest. Not a promotion.
**Audit status:** PASS
**Backtest execution:** NOT RUN
**Paid Odds API requests this audit:** 0
**Persisted data modified:** NO

Machine-readable twin: `workers/ml/reports/walk-forward-2024-2026-protocol.json`.

This document freezes how a future full walk-forward evaluation **must** be run
over the available football history from 2024 through the latest verified 2026
rows. It does **not** execute that evaluation.

It does **not** restart historical Odds API collection.
It does **not** change Elo hyperparameters.
It does **not** retrain or promote `football-elo-v1-candidate`.

Implementations audited from unmerged code at
`origin/agent/data/final-oos-odds-batch` commit
`1cde8f701e2fcdfd85f9574983b76abd810003cc`.
Verified SQL inventory numbers are taken from that commit's
`workers/ml/reports/oos-odds-final-batch.json` and from the collection-stop
audit (`docs/qa/historical-2024-2026-collection-audit.md` on
`cursor/historical-odds-cost-coverage-audit-2e1c`). They were **not**
re-queried from live PostgreSQL on this VM.

Discarded unverified claims (not facts): 637/1348 requests, 436 new requests,
~1114 PIT records, ~4.8 hours remaining, or credit math derived from those
numbers.

---

## 1. Executive summary

A genuine 2024→2026 historical evaluation **cannot** score the frozen candidate
`football-elo-v1-candidate` on 2024 or 2025. That artefact's draw transform was
fit on `event_at < 2026-01-01` and its sigmoid calibrator was fit/selected on
`event_at < 2026-07-01`. Scoring it before `2026-07-01T00:00:00Z` is in-sample
reconstruction, not OOS.

The recommended protocol is therefore a **new expanding walk-forward** that
emits a **new artefact per step**, with frozen hyperparameters and frozen
calibration *method*:

| Frozen (do not retune) | Refit per step |
| --- | --- |
| Elo K=20, HA=80, initial=1500, scale=400 | Causal Elo ratings (sequential PIT walk) |
| `canonical_team_id` identity | Draw transform `draw_base` / `draw_decay` on TRAIN only |
| Calibration method = sigmoid (Platt OvR) | Sigmoid coefficients on CALIBRATION only |
| Feature schema `football-1x2-features-0.3` | Nothing on OOS labels |
| Value Engine `value-engine-0.1` | — |
| AI Picks `ai-picks-0.1` thresholds | — |

Two evaluations stay strictly separate:

- **A. ML prediction** — every finished labeled match with valid pre-match Elo.
  Missing odds are not a failed prediction.
- **B. Value / AI Picks** — only matches where prediction + complete pre-kickoff
  1X2 PIT odds + Value Engine + eligibility all succeed. Missing odds are an
  exclusion, never fabricated.

**GO / NO-GO for running the eventual backtest:** **NO-GO**.

Meaning of NO-GO: the protocol is defined, but this VM does not currently hold
the parquet or PostgreSQL needed to execute it, and 2024/2025 PIT odds coverage
is `UNAVAILABLE FROM CURRENT PERSISTED STATE`. NO-GO does **not** mean the
model is unprofitable, unvalidated, or should be promoted. The candidate
remains `promoted_to_production = false`.

---

## 2. Verified data inventory

Live PostgreSQL and the dataset parquet are **not present on this VM**
(port 5432 closed; `workers/ingestion/var/football-1x2-history.parquet`
absent). Inventory below is report-backed, not a live SQL recount.

### 2.1 Authoritative persisted SQL snapshot (final odds batch)

Source: `workers/ml/reports/oos-odds-final-batch.json` @ `1cde8f7`.

| Item | Count | Notes |
| --- | ---: | --- |
| Canonical matches | 7622 | SQL `matches`. Not all are labeled ML rows. |
| Live odds snapshots | 43280 | SQL `odds_snapshots` with `data_mode=live`. **Not matches.** |
| Mock odds snapshots | 0 | Isolation holds. |
| Odds selections | 129839 | SQL `odds_selections`. **Not matches.** |
| Raw Odds API payloads | 203 | `raw_payloads` where `provider=the_odds_api`. **Not matches.** |
| Odds ingestion runs | 7 | `the_odds_api` runs. |
| Orphan odds | 0 | |
| Duplicate snapshot ids | 0 | |
| Last paid historical batch | 10 requests / 100 credits | MLS `h2h` / region `eu` |
| New canonical OOS matches from that batch | 0 | Coverage gain was free MLS replay |
| Reused historical requests | 77 | |
| Unmatched Odds API names (quarantined) | 3738 | No guessing |
| Unmappable CL qualification slots | 15 | Catalog key absent |
| Last verified remaining credits | 17010 | Header at last historical response |

Snapshots must never be counted as matches. 43280 snapshots ≠ 43280 matches.

### 2.2 Canonical match status (dataset-build report, not live SQL)

Source: `docs/ml-dataset.md` snapshot of dataset 0.3 built 2026-09-10 from
PostgreSQL without re-fetching Sportmonks.

| Status | n | Derivation |
| --- | ---: | --- |
| Canonical matches | 7622 | SQL inventory |
| Finished labeled 1X2 rows | 5729 | Parquet `football-1x2-history-0.3` |
| Rejected at dataset build | 1893 | All `not_finished` (1890 scheduled + 3 other) |
| Check | 5729 + 1893 = 7622 | Consistent |

Scheduled/postponed/other **year splits:** `UNAVAILABLE FROM CURRENT PERSISTED STATE`.

### 2.3 Labeled ML rows by calendar year (from frozen split windows)

These are **labeled finished** rows in dataset 0.3, not all canonical matches.
Year is the UTC `event_at` window used by `WALK_FORWARD_BOUNDS`, not the
Sportmonks season label.

| Calendar window (`event_at`) | n | Source |
| --- | ---: | --- |
| 2024-02-22 → 2025-01-01 | 1538 | fold_1 train |
| 2025-01-01 → 2026-01-01 | 2556 | fold_1 val 1305 + fold_2 val 1251 |
| 2026-01-01 → 2026-09-10T02:30:01 | 1635 | fold_3 val 1248 + final_test 387 |
| **Labeled total** | **5729** | 1538+2556+1635 |

Earliest labeled kickoff: `2024-02-22T01:00:00Z`.
Latest labeled kickoff: `2026-09-10T02:30:00Z`.
June 2026 finished matches in 0.3: **0** (real hole, not a missing file).

Canonical matches by calendar year (including unfinished):
`UNAVAILABLE FROM CURRENT PERSISTED STATE`.

### 2.4 Labeled rows by competition (dataset 0.3)

| Competition | n |
| --- | ---: |
| MLS | 1419 |
| La Liga | 801 |
| Premier League | 790 |
| Serie A | 790 |
| Champions League | 662 |
| Ligue 1 | 637 |
| Bundesliga | 630 |
| **Total** | **5729** |

Seasons present in parquet: `2024`, `2024/2025`, `2025`, `2025/2026`, `2026`,
`2026/2027`. Season-label counts beyond the walk-forward validation / test
cards in `football-elo-v1-candidate.summary.json` are not re-derived here.

### 2.5 Historical odds — five distinct objects

| Layer | What it is | Verified count |
| --- | --- | --- |
| A. Raw Odds API events/payloads | Immutable `raw_payloads` | 203 payloads |
| B. Odds snapshots | `odds_snapshots` rows | 43280 live; 0 mock |
| C. Canonical match mappings | Snapshots joined to `matches.id` | 0 orphans; identity quarantines 3738 unmatched names |
| D. Valid pre-kickoff 1X2 snapshots | `available_at <= kickoff`, market 1X2, live, source `the-odds-api-v4` | Counted **per OOS match**, not as a global snapshot total |
| E. Matches with ≥1 valid PIT 1X2 | Dataset-0.3 OOS universe only | **181 / 387 = 46.77%** |

Layer E is **not** year-complete coverage. The collection job that produced
these PIT odds targeted

```text
OOS window = [2026-07-01T00:00:00Z, 2026-09-10T02:30:01Z)
```

Odds coverage by calendar year 2024 / 2025 / rest of 2026, and coverage of the
5729 labeled rows outside that window:
`UNAVAILABLE FROM CURRENT PERSISTED STATE`.

Do not infer 2024–2025 Value coverage from 43280 snapshots.

### 2.6 OOS-window odds coverage (2026-07-01 → 2026-09-10 only)

| Competition | OOS matches | Valid PIT 1X2 | Coverage |
| --- | ---: | ---: | ---: |
| Premier League | 30 | 30 | 100.00% |
| Ligue 1 | 27 | 24 | 88.89% |
| Serie A | 30 | 22 | 73.33% |
| MLS | 139 | 80 | 57.55% |
| Bundesliga | 18 | 7 | 38.89% |
| La Liga | 41 | 12 | 29.27% |
| Champions League | 102 | 6 | 5.88% |
| **Total** | **387** | **181** | **46.77%** |

Uncovered 206: 203 `no_live_1x2_snapshot` + 3 isolated Paris FC identity holds.
Ligue 1 isolated count in the coverage table is 4 (Paris FC isolation + one
inverted home/away identity hold on a separate match).

Provider / market / region used for historical collection:

- Provider: The Odds API v4 / source `the-odds-api-v4`
- Market requested: `h2h` → canonical `1X2`
- Region: `eu`
- Bookmakers observed on the **last persist batch** (not a global census of
  43280): 24 books including Pinnacle, Betfair EX EU, Unibet, Winamax, etc.
  Bookmaker identity is **not** a PIT selection criterion.

PIT timestamps among the 181 valid OOS matches:

- Earliest `earliest_odds_available_at`: `2026-07-16T23:23:52Z`
- Latest `latest_odds_available_at`: `2026-09-09T23:55:30Z`
- Every valid match has **multiple** snapshots (min 10, max 199, mean 79.3)
- 176 post-kickoff snapshots persisted on **11 MLS** matches; PIT selection
  (`available_at <= kickoff`) does not use them (`selected_post_kickoff = 0`)

`snapshot_age_seconds` in the coverage JSON is `kickoff - latest_available_at`.
On those 11 MLS matches the **latest** snapshot is post-kickoff, so the field
is negative. That is a **coverage-report metric defect**, not evidence that
PIT selection leaked. Freshness for Value/AI Picks **must** be computed from
the **selected** snapshot (`available_at <= cutoff`), not from latest.

### 2.7 PIT feature availability (ML)

Dataset 0.3: `elo_available = 1` on all 5729 labeled rows. Candidate features
are `home_elo_pre`, `away_elo_pre`, `elo_diff` only. Form / goals / H2H exist
in the schema but are **not** consumed by the Elo candidate.

Parquet SHA-256 (pinned):
`0a11a3712c30e4f37c0ac0a75e0e321b70f93565fc994105d613a1361ce9d3c5`.

`data_mode` on labeled rows: `live` only (loader refuses `mock`).

---

## 3. Data lineage

Traced from code, not filenames.

```text
Sportmonks Football API
  → workers/ingestion raw store (immutable envelopes)
  → validation / normalisation / quarantine
  → PostgreSQL canonical entities
       matches, teams, competitions, seasons
  → PointInTimeStore (available_at < cutoff AND event_at < cutoff)
  → reconstruct_pre_match_elo (snapshot at event_at, update at event_at+3h)
  → build_ml_dataset → football-1x2-history-0.3 parquet
  → predicta_ml load (version + sha256 + live-only guards)
  → Elo 1X2 (draw transform on TRAIN) + sigmoid on CALIBRATION
  → FootballPredictionService (ParquetPitFeatureStore, cutoff == kickoff)
  → OddsService / SqlOddsRepository
       last complete 1X2 with available_at <= cutoff
       ordered by (available_at, collected_at, snapshot.id)
  → app.value_engine.calculator (value-engine-0.1, Decimal)
  → AiPicksEngine (deterministic eligibility + ranking)
  → FootballAnalystService (explanation only; grounding assert)
```

Authoritative modules (final-oos-odds-batch @ `1cde8f7`):

| Concern | Implementation |
| --- | --- |
| Historical football dataset | `predicta_ingestion.ml.dataset` / parquet 0.3 |
| PIT feature store (data) | `predicta_ingestion.pit.store.PointInTimeStore` |
| PIT feature store (serving) | `app.predictions.features.ParquetPitFeatureStore` |
| Elo feature generation | `predicta_ingestion.ml.elo.reconstruct_pre_match_elo` and `predicta_ml.models.elo_walk` |
| Model training | `predicta_ml.models.elo.EloBaseline` |
| Calibration | `predicta_ml.calibration.methods.SigmoidCalibrator` |
| Prediction service | `app.predictions.service.FootballPredictionService` |
| Historical odds ingest | `predicta_ingestion.oos_historical_odds` / `oos_final_odds_batch` |
| Odds PIT selection | `app.odds.service.OddsService.market_at` |
| Value Engine | `app.value_engine.calculator` — **not** deleted `app.domain.value_engine` |
| AI Picks | `app.ai_picks.service.AiPicksEngine` |
| Existing OOS evaluation | `predicta_ml.oos` + `app.backtesting.production_oos_sql` |
| Registries | `workers/ml/reports/football-elo-v1-candidate.*.json` |

Deleted legacy Value Engine: `app.domain.value_engine.py` is absent; test
`test_legacy_domain_module_is_gone` enforces that.

The LLM does not sit on this path except as `FootballAnalystService` narrator
after Value/Picks exist.

---

## 4. PIT / leakage audit

Fail-closed rules the future backtest must keep:

```text
feature.available_at  <  prediction_cutoff
feature.event_at      <  prediction_cutoff
match.event_at        >= prediction_cutoff   (the match being predicted)
odds.available_at     <= prediction_cutoff
odds.available_at     <= kickoff_at
prediction_cutoff     == kickoff_at          (frozen pre_kickoff policy)
```

| Check | Result | Evidence |
| --- | --- | --- |
| Historical Elo uses only previous matches | PASS | Snapshot kind=0 before update kind=1; target never updates its own pre-match Elo |
| Current match excluded from rolling / H2H | PASS | Dataset builder + `PointInTimeStore.features_for_match` |
| Future results cannot change historical ratings | PASS | Update at `event_at+3h`; sort `(timestamp, kind, match_id)` |
| Post-kickoff odds cannot be selected | PASS | OddsService filters `available_at <= cutoff`; OOS helper raises if only future quotes exist |
| Post-kickoff score/status cannot enter features | PASS | Labeled parquet has no target-match scores as features; unfinished rows rejected |
| Entity resolution does not use future information | PASS | Static aliases + quarantine; unmatched names are not guessed |
| Calibration does not overlap training (per artefact) | PASS if this protocol is followed | Candidate's own calib is 2026-01-01→2026-07-01; walk-forward refits per step |
| OOS labels not used for fitting | PASS if this protocol is followed | Frozen candidate OOS starts 2026-07-01; walk-forward OOS is after each step's calib |
| Value odds available at or before cutoff | PASS | Canonical OddsService policy |
| No future snapshot selected accidentally | PASS in published selector | `selected_post_kickoff = 0` on the 181-match coverage card |

**Asymmetry (not a BLOCKER):** feature PIT is strict `< cutoff`; odds PIT is
`<= cutoff`. This is the published production contract
(`docs/ml/production-oos-protocol.md`). The walk-forward must not invent a
stricter `cutoff_at < kickoff_at` feature policy: `ParquetPitFeatureStore`
rejects it.

**Non-blocking reporting defect:** coverage `snapshot_age_seconds` uses the
latest snapshot, including post-kickoff. Recompute freshness from the selected
PIT snapshot.

**BLOCKERS found in code paths:** none.

Scoring `football-elo-v1-candidate` on 2024–2025 **would** be a BLOCKER if
someone labeled it OOS. This protocol forbids that. Use per-step artefacts.

---

## 5. Historical odds coverage

### Prediction coverage versus odds coverage

| Concept | Universe | Currently verified |
| --- | --- | --- |
| **Prediction coverage** | Finished labeled matches with PIT Elo | 5729 / 5729 in dataset 0.3 |
| **Odds coverage** | Those matches with a valid pre-kickoff complete 1X2 PIT snapshot | **181 / 387** inside the 2026-07-01 OOS window only |

They are not the same thing. A match can be a valid ML OOS row and still have
`odds_unavailable`. That is an exclusion for evaluation B, never a prediction
failure for evaluation A.

### Coverage report the eventual backtest must emit

For **each walk-forward OOS step**, and globally:

- total OOS matches (prediction universe)
- matches with valid PIT odds
- odds coverage %
- coverage by year — emit n; if SQL cannot group, write
  `UNAVAILABLE FROM CURRENT PERSISTED STATE` (do not infer)
- coverage by competition
- coverage by market (1X2 only for V0.1)
- coverage by provider/region (`the-odds-api-v4` / `eu` / `h2h`)
- matches with multiple snapshots
- earliest / latest **selected** pre-kickoff snapshot
- snapshot freshness = `cutoff_at - selected.available_at` (never latest)
- excluded matches by reason (`no_live_1x2_snapshot`, `incomplete_market`,
  `identity_quarantine`, `isolated_team`, `stale_odds`, …)

Year/competition odds coverage outside the 387-match window is currently
unavailable. Do not fill it from 43280 snapshot rows.

---

## 6. Recommended walk-forward protocol

### 6.1 Why the frozen 2026 OOS protocol is not reused as the 2024–2026 design

The existing production OOS protocol
(`docs/ml/production-oos-protocol.md`) is the correct **frozen-candidate
scorecard** for `event_at >= 2026-07-01`. It is **not** a historical
walk-forward: 2024 and 2025 are rejected periods for that artefact.

### 6.2 Alternatives considered

| Id | Idea | Verdict |
| --- | --- | --- |
| P0 | Score frozen candidate on 2024–2026 | **Rejected.** In-sample before 2026-07-01. |
| P1 | Expanding walk-forward, nested TRAIN → CALIB → OOS, frozen K/HA/sigmoid method | **Selected.** |
| P2 | Rolling 12-month train | Rejected. Discards 2024 just when 2026 sample is smallest. |
| P3 | Season-label folds (2024/25 vs 2025/26) | Rejected. MLS is calendar-year; CL spans; existing splits are UTC calendar by design. |

### 6.3 Selected protocol `walk-forward-2024-2026-v1`

**Window type:** expanding from `2024-02-22T00:00:00Z`.
**Retrain frequency:** once per step (three steps), at that step's train cutoff.
**Calibration frequency:** once per step, after train, before OOS. Method is
frozen; only coefficients are refit.
**Cutoff:** `cutoff_at = kickoff_at = event_at` (`pre_kickoff`).
**Elo state:** one continuous causal walk from dataset start; **not** reset
per step. Sequential updates after a step's train cutoff may enter a later
OOS match's pre-match Elo iff `event_at < cutoff` of the match being
predicted. The match being predicted is never included.
**Draw transform:** refit on that step's TRAIN_FIT labels only.
**Sigmoid:** refit on that step's CALIBRATION labels only. Do **not** re-run
method selection (raw vs sigmoid vs isotonic) on later data.

#### Step WF-1 — first true OOS after 2024

| Role | `event_at` window (UTC, end exclusive) | n |
| --- | --- | ---: |
| TRAIN_FIT | `[2024-02-22, T_calib_start)` | Count from parquet at execution. Floor: ≥1000. |
| CALIBRATION | trailing TRAIN rows so `n_calib ≥ 200` and TRAIN_FIT keeps ≥1000 | Count from parquet. Currently **UNAVAILABLE** as an exact integer. Feasible because fold_1 train n=1538. |
| TRAIN (draw transform) | `[2024-02-22, 2025-01-01)` | **1538** (verified) |
| OOS | `[2025-01-01, 2025-07-01)` | **1305** (verified) |

`T_calib_start` is the `event_at` of the first trailing calibration match.
It is **not** a hand-picked calendar date. If parquet cannot satisfy the
floors, the step fails closed.

Artefact id: `football-elo-v1-wf-2024-2026-step-1`.

#### Step WF-2

| Role | Window | n |
| --- | --- | ---: |
| TRAIN_FIT (draw transform) | `[2024-02-22, 2025-01-01)` | 1538 |
| CALIBRATION | `[2025-01-01, 2025-07-01)` | 1305 |
| Expanding Elo walk through | `event_at <` each OOS cutoff | sequential PIT |
| OOS | `[2025-07-01, 2026-01-01)` | **1251** |

WF-1 OOS labels may enter WF-2 calibration. That is walk-forward, not leakage
into WF-1.

Artefact id: `football-elo-v1-wf-2024-2026-step-2`.

#### Step WF-3

| Role | Window | n |
| --- | --- | ---: |
| TRAIN_FIT (draw transform) | `[2024-02-22, 2026-01-01)` | 4094 |
| CALIBRATION (fit only) | `[2026-01-01, 2026-07-01)` | 1248 (=985+263) |
| OOS | `[2026-07-01, 2026-09-10T02:30:01)` | **387** |

Do **not** re-select sigmoid vs isotonic on 2026-05-01→2026-07-01. That window
is calibration **fit** for this new artefact, not a second method bake-off.

Artefact id: `football-elo-v1-wf-2024-2026-step-3`.

Never overwrite `football-elo-v1-candidate`. Never set
`promoted_to_production = true`.

### 6.4 Frozen-candidate scorecard (separate, already defined)

Keep `docs/ml/production-oos-protocol.md` as a **distinct** card:

- Same 387-match window as WF-3 OOS
- Uses the **frozen** joblib, not the WF-3 sibling artefact
- May be compared to WF-3 prediction metrics as a sensitivity check
- Must not be mixed into walk-forward averages as if it were another fold

### 6.5 What this protocol will not do

- Daily or weekly retraining
- Hyperparameter search on OOS
- Threshold search on OOS (`minimum_edge/ev/p` stay 0; max odds age 24h)
- Fabricating odds for 2024–2025
- Calling The Odds API

---

## 7. ML evaluation protocol (evaluation A)

Universe: every finished labeled match in the step's OOS window with valid
pre-match Elo. Dataset 0.3 currently has Elo on every labeled row.

Metrics (already implemented in `predicta_ml.backtesting.metrics` /
`predicta_ml.oos.metrics`):

- Log loss
- Multiclass Brier
- Accuracy (with the known caveat that Elo 1X2 never argmaxes DRAW)
- ECE (10 bins) and class-level calibration / one-vs-rest Brier
- Prediction count n, always
- Confusion matrix
- Frequency baseline on the **train** prior, applied to OOS (not refit on OOS)
- By competition and by calendar year / season, each with n

Missing odds do **not** drop the row from evaluation A.

Do not call this layer “profitable” or “validated for production”.

---

## 8. Value / AI Picks evaluation protocol (evaluation B)

Universe: evaluation A row **and**

1. valid complete pre-kickoff 1X2 snapshot (`available_at <= cutoff`)
2. source `the-odds-api-v4`, `data_mode=live`, market `1X2`
3. Value Engine `value-engine-0.1` succeeds
4. AI Picks v0.1 eligibility passes for at least one selection

Canonical formulas (`app.value_engine.calculator`):

```text
implied_probability = 1 / decimal_odds
overround           = sum(implied_probability)          # not (sum - 1)
no_vig_probability  = implied_probability / overround
edge                = model_probability - implied_probability
EV                  = model_probability * decimal_odds - 1
```

Decimal arithmetic. Last 1X2 component absorbs no-vig rounding so the simplex
sums to exactly 1.

AI Picks ranking key (deterministic, no LLM):

```text
(-opportunity_score, -ev, -edge, -data_freshness, match_id, selection)
opportunity_score = ev + edge
```

Published thresholds (not optimized on any OOS window):

| Threshold | Value |
| --- | --- |
| `minimum_edge` | 0 |
| `minimum_ev` | 0 |
| `minimum_model_probability` | 0 |
| `maximum_odds_age` | 24h |
| Stake | 1 unit per eligible pick |

Metrics:

- eligible matches
- number of picks
- hit rate
- theoretical ROI and units won/lost
- max drawdown
- EV distribution and edge distribution
- odds coverage (and uncovered-by-reason)
- exclusions by reason (`negative_ev`, `stale_odds`, `invalid_odds`,
  `incomplete_market`, `pit_unavailable`, `prediction_unavailable`, …)

Never treat missing odds as a failed prediction.
Never fabricate odds.
Never use the deleted domain Value Engine.

**2024 and 2025 Value/AI Picks:** cannot be scored until a live SQL inventory
proves PIT odds exist for those OOS windows. Today that inventory is
unavailable. WF-3 (2026-07-01 window) has 181/387 verified PIT matches; that
is odds coverage, not an AI Picks count. AI Picks still require eligibility.

---

## 9. Statistical / sample-size rules

Reuse existing constants:

| Rule | n | Meaning |
| --- | ---: | --- |
| `SMALL_SAMPLE_N` / `INSUFFICIENT_SAMPLE_N` | 30 | Flag segment; no strong claim |
| `ROBUST_PROFITABILITY_N` | 250 | Below this, profitability language is forbidden |

Every competition/year segment reports n.

Language:

| Evidence | Allowed language |
| --- | --- |
| Any n | Descriptive performance (log loss, Brier, n) |
| n < 30 | `insufficient evidence` for that slice |
| Picks n < 250 | Descriptive ROI only; **not** “profitable”, **not** “validated” |
| Picks n ≥ 250 and pre-registered thresholds | May discuss statistical weight; still not a production promotion |

Do not hide small samples (Bundesliga OOS n=18, Ligue 1 n=27, CL odds n=6).

Previous frozen OOS Value runs (`production-oos-backtest*.md`) already
concluded `INSUFFICIENT OOS EVIDENCE`. This protocol does not reopen those
ROI numbers as walk-forward results. The 181/387 odds card was **not**
followed by a new backtest (collection-stop audit left it unrun).

---

## 10. Reproducibility requirements

The eventual backtest must refuse to start unless this fingerprint matches.

| Field | Frozen value / rule |
| --- | --- |
| Protocol id | `walk-forward-2024-2026-v1` |
| Dataset version | `football-1x2-history-0.3` |
| Dataset SHA-256 | `0a11a3712c30e4f37c0ac0a75e0e321b70f93565fc994105d613a1361ce9d3c5` |
| Feature schema | `football-1x2-features-0.3` |
| Candidate (untouched) | `football-elo-v1-candidate`, status `candidate`, `promoted_to_production=false` |
| Candidate calibration | sigmoid (artefact) |
| Walk-forward artefacts | `football-elo-v1-wf-2024-2026-step-{1,2,3}` |
| Implementation SHA | `1cde8f701e2fcdfd85f9574983b76abd810003cc` (audit basis) plus the SHA of the branch that actually runs |
| Cutoff protocol | `pre_kickoff`; `cutoff_at == kickoff_at` |
| Odds dataset fingerprint | SQL counts in §2.1 + `plan_sha256=36e100a576fcbb1f7523d113a6bceaf9ceab2d759362a7ecec3aa4f9c1ebc653` for the last collection plan |
| Value Engine | `value-engine-0.1` |
| AI Picks | `ai-picks-0.1` |
| Thresholds | edge 0, ev 0, p_model 0, max age 86400s, `optimized_on_oos=false` |
| Random seed | 42 (sigmoid Platt `random_state`; draw L-BFGS-B is deterministic given train) |
| Elo hyperparameters | K=20, HA=80, initial=1500, scale=400, update delay 3h |

Same match + same cutoff + same inputs must reproduce the same probabilities,
selected snapshot id, edge, EV, and pick rank. `generated_at` / `request_id`
are excluded from the fingerprint.

---

## 11. Known limitations

1. This Cloud Agent VM has no PostgreSQL volume and no parquet. Year splits of
   the 7622 canonical matches cannot be recomputed live.
2. Historical odds collection was scoped to the 387-match 2026-07-01 window.
   2024–2025 PIT odds coverage is unknown and must not be invented.
3. Identity blockers (3738 unmatched names; missing CL qualification sport
   key; Paris FC isolation) cap further paid odds gain. Collection remains
   STOPPED.
4. `available_at` is not a parquet column; Elo uses `event_at+3h`.
5. Standings, injuries, lineups, xG are not in dataset 0.3 features.
6. Elo 1X2 never argmaxes DRAW (HA=+80 geometry). Log loss still scores DRAW.
7. Sigmoid helped calibration_select and hurt the 387-match test for the
   frozen candidate. Walk-forward keeps the method frozen; it may still hurt
   some steps. Report raw **and** sigmoid on each OOS, but the official step
   artefact uses sigmoid.
8. Coverage JSON age field is not PIT freshness.
9. Unmerged ML/odds/value/picks code is not on `main`. Execution must run
   from a tree that contains those modules (audit basis `1cde8f7`) or a
   later merge of that lineage.
10. Previous live-SQL OOS backtest used 114/387 odds, not 181/387. It must
    not be quoted as the 181-coverage Value result.

---

## 12. Explicit GO / NO-GO

**GO** here would mean only: “the protocol and persisted data are sufficiently
defined to run the backtest.”

| Decision | Result |
| --- | --- |
| Freeze this protocol | **YES** |
| Run the walk-forward backtest now | **NO-GO** |
| Retrain / retune / promote | **NO** |
| Restart Odds API collection | **NO** |
| Model is production-ready | **NO** (not implied either way) |
| Model is profitable / validated | **NO** (not evaluated here) |

NO-GO reasons (all must be cleared before execution):

1. Parquet `football-1x2-history-0.3` with the pinned SHA-256 is not on this
   VM.
2. PostgreSQL with the verified 7622 / 43280 / 203 inventory is not on this
   VM.
3. Evaluation B for WF-1 and WF-2 lacks a year-level PIT odds inventory.

After parquet restore, evaluation A (ML only) may be executed **without** new
Odds API requests. Evaluation B remains limited to matches with persisted PIT
odds.

---

## Quality gates run by this audit

Allowed tests only. No paid API. No retrain. No ROI from a new evaluation.

| Suite | Result |
| --- | --- |
| Value Engine + odds PIT unit tests | 34 passed, 2 skipped |
| ML provenance / OOS helpers / calibration / metrics | 27 passed |
| AI Picks + analyst grounding + frozen OOS protocol tests | 33 passed |
| production-oos-sql + prematch runtime | 18 passed, 1 skipped |
| Ingestion PIT / ML dataset leakage | 19 passed; 1 failed (`pyarrow` missing in ingestion venv export test — packaging, not leakage) |

---

AUDIT STATUS: PASS
BACKTEST EXECUTION: NOT RUN
PAID API REQUESTS: 0
DATA MODIFIED: NO

RECOMMENDED NEXT STEP: Restore the SHA-256-pinned `football-1x2-history-0.3`
parquet on an evaluation host that already has the verified PostgreSQL
inventory, then execute **evaluation A only** for `walk-forward-2024-2026-v1`
(no Odds API calls, no Value/AI Picks on 2024–2025 until a live SQL year-level
odds inventory exists).
