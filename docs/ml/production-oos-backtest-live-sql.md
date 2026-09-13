# Production temporal OOS backtest — live SQL odds

**Verdict: `INSUFFICIENT OOS EVIDENCE`.**

`football-elo-v1-candidate` remains a candidate.
`promoted_to_production = false`.

This is the **same frozen OOS protocol** as [production-oos-backtest.md](production-oos-backtest.md).
Only the **odds input source** changed:

- previous run: `persisted-final-test-history-score.json` (analytical quotes)
- this run: PostgreSQL `odds_snapshots` via `SqlOddsRepository` (`data_mode=live`)

Mock odds were not used. New Odds API credits consumed: **0**.

Machine-readable result: `workers/ml/reports/production-oos-backtest-live-sql.json`.
Prediction parity: `workers/ml/reports/prediction_parity.json`.

Command used (zero Odds API credits):

```bash
cd apps/api
python -m app.backtesting production-oos-sql
```

---

## 1. What changed / what did not

| Frozen | This rerun |
| --- | --- |
| Model `football-elo-v1-candidate` | unchanged |
| Elo K / HA / calibration / artefact | unchanged |
| OOS window `2026-07-01` → `2026-09-10T02:30:01Z` | unchanged |
| 387 finished OOS matches | unchanged |
| Value Engine v0.1 formulas | unchanged |
| AI Picks v0.1 thresholds and ranking | unchanged |
| PIT policy (`available_at <= cutoff`, last complete 1X2) | unchanged |
| Odds source | **PostgreSQL live PIT snapshots** |

The 114 / 387 figure from the historical-odds expansion is **matches with valid live PIT 1X2 odds**.
It is **not** an AI Picks count. AI Picks are counted only after prediction → PIT odds → Value Engine → eligibility.

---

## 2. Prediction parity

| | |
| --- | ---: |
| Shared matches | 387 |
| Prediction differences | **0** |
| Max abs delta | 0.0 |
| Result | **PASS** |

Same match universe, model artefact, model version, dataset version, feature schema, cutoff, and probabilities.

---

## 3. Comparison with the previous frozen run

| | Previous | New |
| --- | ---: | ---: |
| OOS matches | 387 | 387 |
| Odds-covered | 53 | 114 |
| Coverage | 13.7% | 29.5% |
| AI Picks | 68 | 143 |
| Eligible matches | 49 | 103 |
| Hit rate | 20.59% | 21.68% |
| ROI | -10.19% | -18.36% |
| Max drawdown | 15.00u | 27.24u |
| Odds source | JSON analytical fixture | PostgreSQL live PIT |

---

## 4. Odds coverage

| | |
| --- | ---: |
| OOS matches | 387 |
| Matches with a valid PIT 1X2 snapshot | 114 |
| Coverage | **29.46%** |
| Live snapshots considered | 8876 |
| Live snapshots eligible | 8876 |
| Live snapshots selected | 114 |
| Live snapshots rejected | 0 |
| Mock odds used | **0** |
| Provider | `the-odds-api-v4` |
| Repository | `SqlOddsRepository` |
| New Odds API credits | **0** |

Rejected snapshot count is 0.
273 OOS matches had no eligible live PIT snapshot
(structured exclusion). That is not an AI Picks count.

---

## 5. Prediction performance (unchanged layer)

Frozen sigmoid Elo on all 387 OOS matches. Odds are not an input to the model.

| Metric | Frozen Elo |
| --- | ---: |
| n | 387 |
| Accuracy | 48.32% |
| LogLoss | 1.0280 |
| Brier | 0.6159 |
| ECE | 0.0629 |

These must remain LogLoss ≈ 1.0280, Brier ≈ 0.6159, Accuracy ≈ 48.32%, ECE ≈ 0.0629.

---

## 6. Value Engine

Canonical `value-engine-0.1` via `app.value_engine.calculator`.
Eligible matches with PIT odds: 114.

On eligible picks:

| | |
| --- | ---: |
| Average model probability | 30.92% |
| Average implied probability | 25.34% |
| Average no-vig probability | 23.98% |
| Average edge | 5.58% |
| Average EV | 0.299 |
| Average odds | 4.69 |

Average EV is not realized profit.

---

## 7. AI Picks

Published `ai-picks-0.1` thresholds. `optimized_on_oos = false`.

| | |
| --- | ---: |
| Matches with odds | 114 |
| Matches with ≥1 eligible pick | 103 |
| Eligible picks | **143** |
| Excluded opportunities | 199 |
| Exclusion reasons | `negative_ev`: 199 |
| Hits | 31 |
| Hit rate | **21.68%** |

---

## 8. ROI / drawdown

Assumptions unchanged: 1 unit per eligible pick; decimal odds; settle `odds − 1`
on a hit, `−1` on a miss; chronological by `(kickoff_at, match_id, selection)`.

| | |
| --- | ---: |
| Realized ROI | **-18.36%** |
| Realized P&L | **-26.25 u** |
| Max drawdown | **27.24 u** |
| Longest losing streak | 11 |
| Profit factor | 0.77 |

Historical ROI does not predict future profit. This sample does not support a profitability conclusion.

---

## 9. League breakdown

Do not draw conclusions from tiny samples.

| Competition | OOS matches | Odds-covered | Coverage | AI Picks | Hit rate | ROI | Drawdown | P&L |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| premier-league | 30 | 30 | 100.0% | 38 | 21.1% | -15.5% | 13.15 u | -5.89 u |
| ligue-1 | 27 | 24 | 88.9% | 32 | 21.9% | 5.2% | 8.00 u | 1.68 u |
| la-liga | 41 | 12 | 29.3% | 15 | 20.0% | -27.5% | 5.73 u | -4.13 u |
| bundesliga | 18 | 7 | 38.9% | 11 | 27.3% | -12.3% | 5.00 u | -1.35 u |
| serie-a | 30 | 22 | 73.3% | 25 | 32.0% | -5.7% | 4.62 u | -1.42 u |
| champions-league | 102 | 6 | 5.9% | 4 | 0.0% | -100.0% | 4.00 u | -4.00 u |
| mls | 139 | 13 | 9.4% | 18 | 11.1% | -61.9% | 11.14 u | -11.14 u |

---

## 10. Leakage checks

All checks **PASS**.

| Check | Result |
| --- | --- |
| cutoff after kickoff | fail-closed; none observed |
| feature `available_at` / `event_at` ≥ cutoff | fail-closed; none observed |
| odds `available_at` after cutoff | fail-closed; none observed |
| post-kickoff odds | fail-closed; none observed |
| outcome used before kickoff | fail-closed; none observed |
| mock odds in result | **0 used** |
| future snapshot selected | fail-closed; synthetic future quote did not change fingerprint |
| duplicate snapshot ambiguity | fail-closed at OddsService PIT selection |
| identity ambiguity | fail-closed; none observed |
| SQL unavailable JSON fallback | refused |

---

## 11. Reproducibility

| | |
| --- | --- |
| Result | **PASS** |
| Fingerprint | `14c1cc9b61ffb59243e27dbee578dd4ea1309a61b1355292254cccdafe9e34d1` |
| Input ids hash | `21728395b106596c74111da29c55086743275ea3896b538abf0ec23b82bde2db` |
| Selected snapshot ids hash | `d6a788b9b87abbc3f2a06ce35eff7ff52984e715b6895748f8e405c2427d99b6` |
| Code version | `0.1.0+0df4ae6` |
| Odds provider | `the-odds-api-v4` |
| Odds repository | `SqlOddsRepository` |

The backtest was executed twice. Results were identical except for paths written after scoring.
`generated_at` / `request_id` are not part of the fingerprint.

---

## 12. Limitations

1. Odds coverage is still 29.5% (< 50% protocol bar).
2. Pick count is 143 (< 250 robust-profitability bar).
3. AI Picks v0.1 thresholds were frozen for this protocol and were not a historically pre-registered trading strategy.
4. Multiple bookmakers can share `available_at`; selection remains last complete
   1X2 by `(available_at, collected_at, snapshot.id)`.
5. Historical ROI does not predict future profit.
6. This task does not promote `football-elo-v1-candidate`.

---

## 13. Final verdict

**`INSUFFICIENT OOS EVIDENCE`.**

Not a promotion. Not an optimization. Measurement only: same frozen protocol, PostgreSQL live PIT odds.

OOS sample insufficient for a robust profitability conclusion unless the protocol bars are met.
