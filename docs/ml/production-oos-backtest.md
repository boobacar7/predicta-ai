# Production temporal OOS backtest

**Verdict: `INSUFFICIENT OOS EVIDENCE`.**

`football-elo-v1-candidate` remains a candidate.
`promoted_to_production = false`.

This report evaluates the frozen prediction → odds → Value Engine → AI Picks
pipeline under [production-oos-protocol.md](production-oos-protocol.md). It
does not retune anything. Machine-readable result:
`workers/ml/reports/production-oos-backtest.json`.

Command used (zero Odds API credits):

```bash
cd apps/api
python -m app.backtesting production-oos
```

---

## 1. Executive summary

The earliest legitimate OOS date for the frozen artefact is
**`2026-07-01T00:00:00Z`**. The selected window is the dataset 0.3
`final_test` partition: **`2026-07-01` → `2026-09-10T02:30:01Z`**.

Five claims are reported separately:

| Layer | Sample | Result |
| --- | ---: | --- |
| **A. Model OOS prediction** | 387 finished matches | Accuracy 48.32%, LogLoss 1.0280, Brier 0.6159, ECE 0.0629 |
| **B. Historical odds availability** | 53 / 387 matches | 13.7% coverage; Premier League + Ligue 1 only |
| **C. OOS Value Engine** | 53 matches with PIT odds | Canonical `value-engine-0.1`; 91 opportunities excluded (`negative_ev`) |
| **D. OOS AI Picks** | 68 picks / 49 matches | Hit rate 20.59% (14/68) |
| **E. Realized historical ROI** | 1 unit per pick | ROI −10.19% (−6.93 u), max drawdown 15.00 u |

OOS prediction metrics match the candidate registry `test_chosen` / sigmoid
test. That is expected: this window **is** the held-out test partition.

Odds coverage is too thin, and pick count (68) is below the 250-pick robustness
bar, so this run cannot support a profitability conclusion.

> OOS sample insufficient for a robust profitability conclusion.

---

## 2. Model provenance

Read from `workers/ml/reports/football-elo-v1-candidate.registry.json` and
`....summary.json`. See also
`workers/ml/reports/football-elo-v1-candidate.provenance.json`.

| Field | Value |
| --- | --- |
| Model | `football-elo-v1-candidate` |
| Status | candidate, not production |
| Dataset | `football-1x2-history-0.3` |
| SHA-256 | `0a11a3712c30e4f37c0ac0a75e0e321b70f93565fc994105d613a1361ce9d3c5` |
| Feature schema | `football-1x2-features-0.3` |
| Features | `home_elo_pre`, `away_elo_pre`, `elo_diff` |
| K / HA / scale | 20 / 80 / 400 |
| Draw transform | fit on final_train (`event_at < 2026-01-01`), n=4094 |
| Calibration fit | 2026-01-01 → 2026-05-01, n=985 |
| Calibration select | 2026-05-01 → 2026-07-01, n=263, method=`sigmoid` |
| Artefact created_at | `2026-09-10T17:43:36.436814Z` |
| Code at artefact | `0.1.0+e8b76d7` |
| This run used artefact | yes (`used_artefact=true`) |

Latest training `event_at` exclusive: **`2026-01-01T00:00:00Z`**.

Latest calibration `event_at` exclusive: **`2026-07-01T00:00:00Z`**.

Parquet has no `available_at` column. Elo updates in the data layer use
`event_at + 3h`.

---

## 3. Why the chosen OOS period is valid

Selected window:

```text
start          = 2026-07-01T00:00:00+00:00
end_exclusive  = 2026-09-10T02:30:01+00:00
```

It is valid because:

1. Training labels and the draw transform use only `event_at < 2026-01-01`.
2. The sigmoid calibrator is fit on `event_at < 2026-05-01` and selected on
   `event_at < 2026-07-01`.
3. Every OOS match has `event_at >= 2026-07-01`, so neither fitting step can
   see those labels.
4. The backtest loads the frozen joblib calibrator and does not refit K, HA,
   draw, or sigmoid.
5. PIT Elo features for each match are pre-kickoff (`cutoff_at == kickoff_at`,
   `n_with_pre_match_elo = 387`).

Scoring this window is the same held-out `final_test` used in the candidate
validation report. That is OOS for **prediction**. It is **not** automatically
OOS Value/ROI evidence; those require PIT odds, which exist for only 53
matches.

---

## 4. Why rejected periods are invalid

| Period | Split | Why it is not OOS |
| --- | --- | --- |
| W01 Aug–Sep 2024, W02 Oct–Nov 2024, W03 Dec 2024 | `final_train` | Inside the draw-transform training partition. |
| 2025-01-01 → 2025-07-01 | `fold_1_validation` | Walk-forward validation, not a freeze hold-out. |
| 2025-07-01 → 2026-01-01 | `fold_2_validation` | Same. |
| 2026-01-01 → 2026-05-01 | `calibration_fit` | Sigmoid parameters were estimated here. |
| 2026-05-01 → 2026-07-01, including May 2026 odds pilots | `calibration_select` | Sigmoid was **chosen** here. |

The 2024 expansion (`docs/qa/final-test-history-expansion.md`) remains a
`final_train` reconstruction. Relabeling it as OOS would be a protocol
violation.

---

## 5. Exact temporal protocol

See [production-oos-protocol.md](production-oos-protocol.md).

Summary of the frozen decision contract used in this run:

```text
cutoff_policy              = pre_kickoff
cutoff_at                  = kickoff_at
features                   : available_at < cutoff, event_at < cutoff
odds snapshot              : available_at <= cutoff, last complete 1X2
value_engine_version       = value-engine-0.1
ai_picks_version           = ai-picks-0.1
minimum_edge / ev / p_model = 0 / 0 / 0
maximum_odds_age           = 24h
stake                      = 1 unit per eligible pick
optimized_on_oos           = false
```

Production PIT equals kickoff. This backtest does not invent a stricter
`cutoff_at < kickoff_at` policy, because `ParquetPitFeatureStore` rejects it.

---

## 6. Dataset coverage

387 finished matches with pre-match Elo for every row.

| Competition | n | Small-sample flag |
| --- | ---: | --- |
| Premier League | 30 | |
| Ligue 1 | 27 | yes (`n < 30`) |
| La Liga | 41 | |
| Bundesliga | 18 | yes (`n < 30`) |
| Serie A | 30 | |
| Champions League | 102 | |
| MLS | 139 | |
| **Total** | **387** | |

First OOS kickoff in the parquet: `2026-07-07T16:00:00Z`.
Last: `2026-09-10T02:30:00Z`.

---

## 7. Prediction performance (layer A)

Frozen sigmoid Elo on all 387 OOS matches. No odds required.

| Metric | Frozen Elo | Frequency baseline (fit `event_at < OOS start`) |
| --- | ---: | ---: |
| n | 387 | 387 |
| Accuracy | 48.32% | 45.74% |
| LogLoss | 1.0280 | 1.0667 |
| Brier | 0.6159 | 0.6443 |
| ECE | 0.0629 | 0.0139 |

These Elo numbers match registry `metrics.test_chosen` / `test_sigmoid`.

HOME / DRAW / AWAY (all n ≥ 30):

| Class | n | Precision | Recall | Mean predicted p | One-vs-rest Brier |
| --- | ---: | ---: | ---: | ---: | ---: |
| HOME | 177 | 0.488 | 0.893 | 0.462 | 0.233 |
| DRAW | 99 | 0.000 | 0.000 | 0.262 | 0.189 |
| AWAY | 111 | 0.460 | 0.261 | 0.333 | 0.194 |

Draw is scored in the log-loss but never wins argmax (same geometry as the
model card). That is not a pipeline bug.

By league (do not over-interpret small n):

| Competition | n | Accuracy | LogLoss | Brier | ECE |
| --- | ---: | ---: | ---: | ---: | ---: |
| premier-league | 30 | 43.3% | 1.013 | 0.605 | 0.166 |
| ligue-1 | 27 | 40.7% | 1.100 | 0.666 | 0.049 |
| la-liga | 41 | 46.3% | 0.995 | 0.592 | 0.161 |
| bundesliga | 18 | 44.4% | 0.955 | 0.567 | 0.257 |
| serie-a | 30 | 63.3% | 0.902 | 0.526 | 0.169 |
| champions-league | 102 | 55.9% | 1.010 | 0.604 | 0.118 |
| mls | 139 | 43.2% | 1.077 | 0.650 | 0.036 |

No-value / no-pick baseline realizes 0 units by construction.

---

## 8. Odds coverage (layer B)

| | |
| --- | ---: |
| OOS matches | 387 |
| Matches with a valid PIT 1X2 snapshot | 53 |
| Coverage | **13.7%** |
| Quotes used | 53 |
| Provider | `the-odds-api-v4` |
| New Odds API credits | **0** |

Covered competitions: Premier League and Ligue 1 only (the persisted
final-test historical-odds set). Bundesliga, La Liga, Serie A, Champions
League, and MLS have **zero** OOS odds in this run.

That is an odds-availability fact, not a prediction-quality fact.

---

## 9. Value Engine results (layer C)

Canonical `value-engine-0.1` via `app.value_engine.calculator`.

On the 53 matches with PIT odds, every HOME/DRAW/AWAY selection is valued.
91 opportunities fail the published EV gate (`negative_ev`). Eligible picks
are the remainder (68).

On those 68 eligible selections:

| | |
| --- | ---: |
| Average model probability | 30.85% |
| Average implied probability | 24.94% |
| Average no-vig probability | 23.72% |
| Average edge | 5.90% |
| Average EV | 0.316 |
| Average odds | 4.74 |

Average EV is not realized profit. Realized P&L is reported in section 11.

---

## 10. AI Picks results (layer D)

Published `ai-picks-0.1` thresholds. `optimized_on_oos = false`.

| | |
| --- | ---: |
| Matches with odds | 53 |
| Matches with ≥1 eligible pick | 49 |
| Eligible picks | 68 |
| Excluded opportunities | 91 |
| Exclusion reasons | `negative_ev`: 91 |
| Hits | 14 |
| Hit rate | **20.59%** |

This is the published selection policy evaluated on temporally valid odds. It
is not a claim that the policy was historically pre-registered as a trading
book.

---

## 11. ROI / drawdown (layer E)

Assumptions (explicit):

- 1 unit staked on every eligible pick
- decimal odds, settle `odds − 1` on a hit, `−1` on a miss
- no commission, no limits, no staking plan
- chronological by `(kickoff_at, match_id, selection)`

| | |
| --- | ---: |
| Realized ROI | **−10.19%** |
| Realized P&L | **−6.93 u** |
| Max drawdown | **15.00 u** |
| Longest losing streak | 15 |
| Profit factor | 0.87 |

Historical ROI does not predict future profit.

---

## 12. League breakdown

Prediction: all seven competitions (section 6–7).

AI Picks / ROI exist only where PIT odds exist:

| Competition | Picks | Hits | Hit rate | ROI | P&L |
| --- | ---: | ---: | ---: | ---: | ---: |
| premier-league | 38 | 8 | 21.1% | −15.5% | −5.89 u |
| ligue-1 | 30 | 6 | 20.0% | −3.5% | −1.04 u |
| la-liga | 0 | — | — | — | no odds |
| bundesliga | 0 | — | — | — | no odds |
| serie-a | 0 | — | — | — | no odds |
| champions-league | 0 | — | — | — | no odds |
| mls | 0 | — | — | — | no odds |

Do not treat two-league ROI as a product-level result.

---

## 13. Selection breakdown

HOME / DRAW / AWAY pick slices are all `n < 30` and are marked small-sample
in the JSON (`échantillon insuffisant pour conclure`).

| Selection | n | Hits | Hit rate | ROI | P&L |
| --- | ---: | ---: | ---: | ---: | ---: |
| HOME | 25 | 5 | 20.0% | −24.0% | −6.00 u |
| DRAW | 20 | 3 | 15.0% | −33.3% | −6.65 u |
| AWAY | 23 | 6 | 26.1% | +24.9% | +5.72 u |

AWAY being positive in this slice is **not** a reason to reweight markets.
That would be hindsight optimization.

---

## 14. Leakage checks

All checks **PASS** (`leakage_checks.passed = true`).

| Check | Result |
| --- | --- |
| cutoff after kickoff | fail-closed; none observed |
| feature `available_at` / `event_at` ≥ cutoff | fail-closed; none observed |
| odds `available_at` after cutoff | fail-closed; none observed |
| post-kickoff odds | fail-closed; none observed |
| outcome used before kickoff | fail-closed; none observed |
| training after train cutoff | rejected by provenance |
| calibration after calibration cutoff | rejected by provenance |
| future snapshot selected | fail-closed; none observed |
| duplicate snapshot ambiguity | fail-closed; none observed |
| identity ambiguity | fail-closed; none observed |
| artefact incompatible with OOS period | rejected (2024 / May 2026 windows raise) |

Tests cover the same contracts, including “future odds must not change an
earlier prediction” and “same match + same cutoff + same inputs => identical
fingerprint”.

---

## 15. Reproducibility

| | |
| --- | --- |
| Result | **PASS** |
| Fingerprint | `73a0e646e44cab5b693ff000ab2c1018288a88963baa7bac3e9582b2de071eab` |
| Input ids hash | `698738157ba37d5004e891bf867fcc14344b9c940a24aa428aa1c1e3a30fdf4f` |

Code version in this run: `0.1.0+1ada5e5` (parent of this branch at generation
time). Artefact code version remains `0.1.0+e8b76d7`.

Manifest fields are in `production-oos-backtest.json` → `manifest`.
`generated_at` / `request_id` are not part of the fingerprint.

---

## 16. Limitations

1. Odds coverage is 13.7% and only two leagues. Value / AI Picks / ROI are
   not comparable to the 387-match prediction sample.
2. 68 picks < 250 required for a robust profitability conclusion.
3. AI Picks v0.1 thresholds were frozen for this protocol but were not a
   historically pre-registered trading strategy. ROI is descriptive.
4. Production PIT uses `cutoff_at == kickoff_at`. A stricter pre-kickoff
   decision time would need a different frozen PIT contract and different
   odds snapshots.
5. Draw never wins argmax; calibration ECE (0.063) is worse than the
   frequency baseline ECE (0.014).
6. Additional 2024 or May 2026 odds would still not be true OOS for this
   artefact.
7. Historical ROI does not predict future profit.

---

## 17. Production recommendation

**`INSUFFICIENT OOS EVIDENCE`.**

Not GO. Not GO WITH CONDITIONS. Not NO-GO on leakage (leakage passed).

Promotion is refused because:

- odds coverage is far below 50%
- pick sample is far below 250
- realized ROI is negative on the only temporally valid odds sample
- the candidate was never in scope for promotion in this task

Additional Odds API credits are **not** required to prove that
`2026-07-01` is the legitimate freeze. They would only be justified later,
and only to collect **more PIT odds inside** `2026-07-01` → `2026-09-10`
(currently uncovered leagues). Collecting 2024 or May 2026 odds would not
create a larger true-OOS sample for this artefact.

Protocol implemented and validated, but insufficient temporally valid
historical odds exist to make a profitability conclusion.
