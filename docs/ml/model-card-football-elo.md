# Model card — Football Elo 1X2 (candidate)

**Status: `candidate`. Not production. Not champion. Not published to the backend.**

This card describes `football-elo-v1-candidate`. It does not guarantee future
results. Predictions are statistical probabilities, never certainties, and
PREDICTA is not a bookmaker.

Full scientific report: [elo-candidate-validation.md](elo-candidate-validation.md).

## Model version candidate

| Field | Value |
| --- | --- |
| `model_version` | `football-elo-v1-candidate` |
| Status | `candidate` |
| Sport / market | Football / 1X2 |
| Seed | 42 |
| Code version at validation | `0.1.0+e8b76d7` |
| Dataset SHA-256 | `0a11a3712c30e4f37c0ac0a75e0e321b70f93565fc994105d613a1361ce9d3c5` |

## Dataset version

`football-1x2-history-0.3` / `football-1x2-features-0.3`.

5729 finished matches, 7 competitions, period 2024-02-22 → 2026-09-10 UTC.
Live Sportmonks only. No odds, no standings, no synthetic rows.

## Features

Only pre-match Elo already computed in the frozen dataset:

- `home_elo_pre`
- `away_elo_pre`
- `elo_diff` (`home_elo_pre - away_elo_pre`, without the +80 home-advantage term)

`elo_available` is constant 1 and unused. Form, goals, H2H and match counts are
not used by this candidate.

## Parameters

| Parameter | Value | Role |
| --- | --- | --- |
| Initial rating | 1500 | Data-layer Elo walk |
| K | 20 | Data-layer Elo walk |
| Home advantage | +80 | Elo update and 1X2 conversion |
| Scale | 400 | Logistic Elo scale |
| Draw base | 0.2774 | Fit on final train only |
| Draw decay | 1.1096 | Fit on final train only |
| Calibration | sigmoid (chosen on calibration_select) | Not re-chosen on test |

1X2 conversion (P(Draw) always emitted, never dropped):

```text
expected_home = 1 / (1 + 10^(-(elo_diff + 80) / 400))
p_draw = clip(draw_base * exp(-draw_decay * |elo_diff| / 400), 0.05, 0.42)
p_home = (1 - p_draw) * expected_home
p_away = (1 - p_draw) * (1 - expected_home)
```

A 5×5 robustness grid (K ∈ {10,15,20,25,30}, HA ∈ {0,40,60,80,100}) was run on
the same temporal folds. The lowest cell (K=30, HA=60, log-loss 1.0123) was
**not** promoted. The candidate stays K=20, HA=80.

## Training methodology

1. Ratings come from the dataset 0.3 causal Elo walk (snapshot at kickoff,
   update at available_at / kickoff+3h).
2. Draw transform is fit by L-BFGS-B on the training window only.
3. Expanding walk-forward, three folds, no random split.
4. Final fit: train < 2026-01-01 (4094 matches).
5. Sigmoid calibrator fit on 2026-01-01 → 2026-07-01, never on the test window.

No XGBoost/LightGBM, no external data, no odds, no Value Engine.

## Temporal validation

| Window | Period (UTC, end exclusive) | n |
| --- | --- | ---: |
| Fold 1 train / val | → 2025-01-01 / → 2025-07-01 | 1538 / 1305 |
| Fold 2 train / val | → 2025-07-01 / → 2026-01-01 | 2843 / 1251 |
| Fold 3 train / val | → 2026-01-01 / → 2026-07-01 | 4094 / 1248 |
| Calibration fit | 2026-01-01 → 2026-05-01 | 985 |
| Calibration select | 2026-05-01 → 2026-07-01 | 263 |
| Final test | 2026-07-01 → 2026-09-10 | 387 |

June 2026 has zero finished matches in 0.3.

## Metrics

Walk-forward mean (dataset Elo, raw probabilities):

| Log-loss | Brier | Accuracy | ECE |
| ---: | ---: | ---: | ---: |
| 1.0179 | 0.6080 | 50.56% | 0.0291 |

Final test:

| Method | Log-loss | Brier | Accuracy | ECE |
| --- | ---: | ---: | ---: | ---: |
| raw | **1.0238** | **0.6124** | **48.84%** | **0.0459** |
| sigmoid | 1.0280 | 0.6159 | 48.32% | 0.0629 |

Sigmoid improves calibration_select (1.0508 vs 1.0589) but **does not improve
the held-out test**. The artefact still stores sigmoid because that method was
chosen without looking at test. This is a reason not to promote.

## Limitations

- Argmax never selects Draw (P(Home) > P(Draw) even at elo_diff=0 because of +80 HA).
- P(Draw) remains in the simplex and is used for log-loss/Brier.
- No xG, lineups, injuries, or odds.
- ~2.5 years of history; MLS volume dominates some windows.
- Small test slices per European league (n=18–41 except Champions League).
- Accuracy is a poor 1X2 metric for this model because Draw is never the mode.

## Known issues

- Sigmoid selected on 263 calibration_select rows does not generalise to the 387-match test (worse log-loss and ECE).
- Test Ligue 1 (n=27) and MLS (n=139) are the weakest test segments by log-loss.
- Bundesliga test ECE 0.24 is noisy (n=18), not a walk-forward collapse.
- No competition collapses vs frequency on walk-forward (margin 0.02).

## Calibration

- Raw probabilities are already reasonably calibrated on walk-forward (ECE 0.029, pooled ECE 0.011).
- Platt/sigmoid OvR + renormalisation helps the small calibration_select window.
- Isotonic was previously shown to degrade this sample size and was not re-run here.
- Draw-class ECE on test raw: 0.021. Draw probabilities sit mostly in [0.10, 0.28].

## No guarantee statement

Model probabilities are estimates, not promises. They must never be presented as
a sure result, a safe bet, or a financial return. Unavailable data is unavailable.
This candidate is not authorised for live inference, backend publication, or
value/EV calculations.
