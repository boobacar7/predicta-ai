# Production temporal OOS protocol

This protocol defines how PREDICTA may claim that a football 1X2 prediction →
odds → Value Engine → AI Picks evaluation is **true temporal out-of-sample
(OOS)** for the frozen candidate `football-elo-v1-candidate`.

It does **not** retune the model, calibration, Value Engine formulas, AI Picks
thresholds, odds matching, PIT semantics, or data ingestion. The candidate
remains `promoted_to_production = false`.

Machine-readable provenance:
`workers/ml/reports/football-elo-v1-candidate.provenance.json`.

Implementation (isolated module; production engines are reused, not rewritten):

- `workers/ml/src/predicta_ml/oos/`
- `apps/api/app/backtesting/production_oos.py`

Commands:

```bash
cd workers/ml
python -m predicta_ml oos-backtest --dataset ../ingestion/var/football-1x2-history.parquet

cd apps/api
python -m app.backtesting production-oos
```

The API command attaches previously persisted Odds API quotes (zero new credits)
and the production Value Engine calculator.

---

## Frozen provenance (read from artefacts, not inferred)

Source cards:

- `workers/ml/reports/football-elo-v1-candidate.registry.json`
- `workers/ml/reports/football-elo-v1-candidate.summary.json`
- local joblib (gitignored): `workers/ml/var/registry/football-elo-v1-candidate/artefact.joblib`

| Item | Value |
| --- | --- |
| Model | `football-elo-v1-candidate` |
| Status | `candidate` (`promoted_to_production = false`) |
| Dataset | `football-1x2-history-0.3` |
| Dataset SHA-256 | `0a11a3712c30e4f37c0ac0a75e0e321b70f93565fc994105d613a1361ce9d3c5` |
| Feature schema | `football-1x2-features-0.3` |
| Code at artefact creation | `0.1.0+e8b76d7` |
| Artefact `created_at` | `2026-09-10T17:43:36.436814Z` |
| Hyperparameters | K=20, HA=80, scale=400, initial=1500 |
| Draw transform | `draw_base` / `draw_decay` fit on final_train only |
| Calibration | sigmoid (Platt / OvR), fit then selected as below |

| Window | `event_at` (UTC, end exclusive) | n | Role |
| --- | --- | ---: | --- |
| Train | `2024-02-22` → `2026-01-01` | 4094 | Labels + draw-transform fit |
| Calibration fit | `2026-01-01` → `2026-05-01` | 985 | Sigmoid calibrator **fit** |
| Calibration select | `2026-05-01` → `2026-07-01` | 263 | Sigmoid vs alternatives **chosen** |
| Final test / OOS | `2026-07-01` → `2026-09-10T02:30:01` | 387 | Held-out scoring only |

`available_at` is not a parquet column. Data-layer Elo updates use
`event_at + 3h`. Training labels satisfy `event_at < 2026-01-01T00:00:00Z`.

**Temporal freeze / earliest legitimate OOS date:**
`2026-07-01T00:00:00Z` (`calibration_select.end_exclusive`).

The joblib file was materialized on `2026-09-10`, after the last OOS kickoff in
dataset 0.3. That timestamp is **not** the temporal freeze. Parameters and the
sigmoid calibrator were estimated only on `event_at < 2026-07-01`. Running the
frozen artefact on earlier matches is **not** OOS.

---

## A. TRAIN

Only information with

```text
event_at < T_train_cutoff
T_train_cutoff = 2026-01-01T00:00:00Z
```

may enter model training, including the Elo 1X2 draw transform.

K and home advantage were frozen from dataset 0.3 (`K=20`, `HA=80`) and must
not be changed by this protocol.

Causal Elo rating updates for a later match may use finished matches that
occurred after the train cutoff, provided each update satisfies
`event_at < cutoff_at` for the match being predicted. That is sequential PIT
scoring, not retraining.

---

## B. CALIBRATION

Calibration must also respect time.

```text
fit:    event_at < 2026-05-01T00:00:00Z
select: event_at < 2026-07-01T00:00:00Z
calibration_cutoff = 2026-07-01T00:00:00Z
```

No future observations. The calibrator is loaded from the frozen artefact and
is never refit on OOS rows.

---

## C. FREEZE

At the OOS start date the following are frozen:

| Component | Frozen version / policy |
| --- | --- |
| Model | `football-elo-v1-candidate` |
| Calibration | sigmoid chosen on calibration_select |
| Feature schema | `football-1x2-features-0.3` |
| Value Engine | `value-engine-0.1` |
| AI Picks | `ai-picks-0.1` |
| Thresholds | `minimum_edge=0`, `minimum_ev=0`, `minimum_model_probability=0`, max odds age 24h |
| Odds provider | `the-odds-api-v4` |
| Odds selection | last complete 1X2 snapshot with `available_at <= cutoff`, ordered by `(available_at, collected_at, snapshot.id)` |
| Cutoff policy | production `pre_kickoff` |

Thresholds are **not** optimized on the OOS window. If they were not
historically pre-registered as a trading strategy, ROI is descriptive, not a
pre-registered system result.

---

## D. OOS PREDICTION

A match may enter the OOS sample only if:

```text
event_at >= 2026-07-01T00:00:00Z
event_at < oos_end
```

Production PIT is `pre_kickoff`:

```text
cutoff_at == kickoff_at == event_at
```

`ParquetPitFeatureStore` rejects `cutoff_at < kickoff_at`. This protocol does
**not** change that production contract.

Prediction features for a match must still satisfy:

```text
available_at < cutoff_at
event_at     < cutoff_at
```

The candidate uses only pre-match Elo already stored in the parquet
(`home_elo_pre`, `away_elo_pre`, `elo_diff`). Those values are the causal
Elo walk (snapshot at kickoff, update at kickoff + 3h). Outcome labels of the
match being predicted are evaluation-only and never enter the probability.

The OOS runner fails if `cutoff_at > kickoff_at` or if `cutoff_at != kickoff_at`.

---

## E. OOS ODDS

Only snapshots satisfying the published OddsService policy may be used:

```text
available_at <= cutoff_at
available_at <= kickoff_at
market = 1X2
complete HOME/DRAW/AWAY decimal odds > 1
```

Never use:

- closing odds that were not available at cutoff
- post-kickoff odds
- later snapshots
- a final/settlement quote reconstructed as an earlier decision

Bookmaker identity is not a selection criterion. Pinnacle is not preferred.
Duplicate snapshot ids or disagreeing `(match_id, available_at, collected_at)`
payloads fail closed.

This protocol does not spend Odds API credits. Historical quotes are reused
from persisted analytical datasets whose `temporal_split` is `final_test` and
whose kickoff is on or after OOS start.

---

## F. VALUE ENGINE

Use canonical `value-engine-0.1` exactly:

- implied probability
- overround
- no-vig probability
- edge
- expected value (EV)

The OOS adapter (`ProductionValueCalculator`) delegates to
`app.value_engine.calculator`. It must not reimplement formulas.

---

## G. AI PICKS

Use deterministic `ai-picks-0.1` eligibility and ranking semantics.

Do not retune `minimum_edge`, `minimum_ev`, `minimum_model_probability`, odds
age, or ranking keys on the OOS period. Do not drop losing leagues or
markets after seeing results.

---

## H. OUTCOME

Outcome is read only after the match has finished, and only for evaluation.

It must never enter prediction features, calibration, odds selection, or
eligibility. Unfinished matches are not OOS rows.

---

## Rejected periods (not OOS)

Do not relabel these as OOS for `football-elo-v1-candidate`:

| Period | Why invalid |
| --- | --- |
| 2024 windows W01–W03 (`final_train`) | Draw transform was fit on `event_at < 2026-01-01`. |
| Walk-forward fold 1 / fold 2 | Validation folds of the development protocol, not a held-out freeze. |
| 2026-01-01 → 2026-05-01 | Sigmoid calibrator was **fit** here. |
| 2026-05-01 → 2026-07-01, including May 2026 odds pilots | Sigmoid method was **selected** here. |

A period is invalid as OOS if the artefact was trained or calibrated using
data from that period or later. Scoring the final artefact on older matches
is in-sample reconstruction, not OOS.

---

## Leakage (fail closed)

The backtest must raise, not silently drop, if:

- prediction cutoff is after kickoff, or is not the frozen `pre_kickoff` cutoff
- `feature.available_at >= cutoff` or `feature.event_at >= cutoff`
- `odds.available_at > cutoff` or post-kickoff
- a future snapshot is selected
- outcome is used before kickoff
- training / calibration windows contain events at or after their cutoffs
- duplicate snapshots create ambiguity
- match identity is empty, duplicated, or disagrees across prediction/odds
- artefact provenance is incompatible with the proposed OOS start

---

## Reproducibility

Same match + same cutoff + same inputs must produce the identical fingerprint.

Changing future odds, or adding a post-cutoff feature observation, must not
change an earlier OOS prediction.

The frozen manifest records dataset, model, calibration, feature schema, Value
Engine, AI Picks, thresholds, OOS window, cutoff policy, odds policy, code
version, and an input-ids hash.

`generated_at` / `request_id` are not part of the fingerprint.

---

## Stake and claims

Default stake: **1 unit per eligible pick**.

Historical ROI does not predict future profit. Prediction quality, odds
coverage, Value Engine evaluation, AI Picks evaluation, and realized ROI are
five separate claims and must not be merged into one “model performance”
number.
