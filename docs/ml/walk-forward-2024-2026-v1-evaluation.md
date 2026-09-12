# Walk-forward 2024–2026 v1 — Evaluation A

**Protocol id:** `walk-forward-2024-2026-v1`
**Evaluation:** A only (ML prediction). Value Engine, AI Picks, ROI, EV, and odds were **not** run.
**Status:** **BLOCKED**

This file is a blocked-run record. It is **not** a completed backtest and must
not be quoted as model performance.

A follow-up on 2026-09-12T18:30:00Z re-checked this Cloud Agent host after a
developer-machine claim that the pinned parquet was verified locally. The file
is still **absent on this VM**. SHA-256 could not be calculated here.
Evaluation A therefore **did not execute**.

---

## 0. Dataset gate (printed before any execution)

Required:

```text
DATASET PATH: workers/ingestion/var/football-1x2-history.parquet
DATASET SHA256: 0a11a3712c30e4f37c0ac0a75e0e321b70f93565fc994105d613a1361ce9d3c5
DATASET VERSION: football-1x2-history-0.3
```

Observed on this host (`cursor`, 2026-09-12T18:30:00Z):

```text
DATASET PATH: workers/ingestion/var/football-1x2-history.parquet
DATASET PATH (absolute checked): /workspace/workers/ingestion/var/football-1x2-history.parquet — MISSING
DATASET SHA256: UNAVAILABLE FROM THIS HOST (file absent)
DATASET SHA256 (required): 0a11a3712c30e4f37c0ac0a75e0e321b70f93565fc994105d613a1361ce9d3c5
DATASET VERSION: UNAVAILABLE FROM THIS HOST (required football-1x2-history-0.3)
ROW COUNT: UNAVAILABLE FROM THIS HOST
DATE RANGE: UNAVAILABLE FROM THIS HOST
GATE: FAIL — Evaluation A refused
```

Also missing: `/tmp/predicta-ml/workers/ingestion/var/football-1x2-history.parquet`.

A developer-machine verification is **not** a SHA-256 measured on this
evaluation host. This agent did not hash any file on
`/Users/boubacar/Development/predicta-ai/...`. It did not copy, download, or
regenerate the parquet.

---

## 1. Why Evaluation A did not run

The frozen protocol refuses to start unless the SHA-256-pinned dataset is
present **on the evaluation host** and hashes to

`0a11a3712c30e4f37c0ac0a75e0e321b70f93565fc994105d613a1361ce9d3c5`.

That parquet is gitignored (`var/` in `.gitignore`). It is not in git, GitHub
Releases, Git LFS, Docker volumes, or this Cloud Agent VM. The recovery search
(`docs/ml/football-1x2-history-0.3-recovery.md`, status `NOT_FOUND`) already
established that. This follow-up confirmed the expected path is still empty.

The protocol forbids substituting another dataset. An empty Postgres rebuild
would not be `football-1x2-history-0.3` with the pinned SHA-256.

Therefore Evaluation A **stopped before any prediction**.

No Odds API request was made. No historical odds were read. No Value Engine
or AI Picks code path ran. Hyperparameters were not changed.
`football-elo-v1-candidate` was not retrained and was not used to score
2024/2025. No walk-forward artefact was written. No artefact was promoted.

---

## 2. What would have been evaluated (not executed)

From the frozen protocol, Evaluation A is ML-only on labeled PIT rows:

| Step | TRAIN | CALIBRATION | OOS | OOS n (protocol) |
| --- | --- | --- | --- | ---: |
| WF-1 | `2024-02-22` → `2025-01-01` (n=1538) | trailing TRAIN, n≥200, train_fit≥1000 | `2025-01-01` → `2025-07-01` | 1305 |
| WF-2 | draw transform on TRAIN through `2025-01-01` | `2025-01-01` → `2025-07-01` (n=1305) | `2025-07-01` → `2026-01-01` | 1251 |
| WF-3 | `2024-02-22` → `2026-01-01` (n=4094) | `2026-01-01` → `2026-07-01` (n=1248), sigmoid fit only | `2026-07-01` → `2026-09-10T02:30:01` | 387 |

Intended prediction count if parquet were present: **1305 + 1251 + 387 = 2943**
OOS rows. That number is a protocol expectation, **not** a result of this run.

Frozen hyperparameters (unchanged, unused):

- Elo initial 1500, K=20, HA=80, scale=400
- Calibration method sigmoid (coefficients refit per step)
- New artefacts `football-elo-v1-wf-2024-2026-step-{1,2,3}`
- Do not score `football-elo-v1-candidate` on 2024/2025 OOS
- Strict PIT chronology; no leakage

---

## 3. Metrics

All metrics are **NOT COMPUTED**.

| Metric | Value |
| --- | --- |
| Predictions | NOT RUN |
| Date range | NOT COMPUTED |
| Log loss | NOT COMPUTED |
| Multiclass Brier | NOT COMPUTED |
| Accuracy | NOT COMPUTED |
| ECE | NOT COMPUTED |
| Class-level calibration | NOT COMPUTED |
| Predicted HOME/DRAW/AWAY distribution | NOT COMPUTED |
| Actual HOME/DRAW/AWAY distribution | NOT COMPUTED |
| By walk-forward step | NOT COMPUTED |
| By competition | NOT COMPUTED |

Do not treat previous candidate cards (walk-forward mean log-loss 1.0179,
frozen-candidate test n=387) as this protocol's Evaluation A. Those used
different artefacts and, for 2024–2025, are not OOS for
`football-elo-v1-candidate`.

---

## 4. Leakage

Leakage checks that require loading parquet and scoring OOS rows were
**NOT RUN**.

Static protocol constraints remain in force and were not relaxed.

---

## 5. Reproducibility fingerprint (blocked)

| Field | Value |
| --- | --- |
| Protocol | `walk-forward-2024-2026-v1` |
| Dataset version | `football-1x2-history-0.3` (required, not loaded) |
| Dataset SHA-256 | required `0a11a3712c30e4f37c0ac0a75e0e321b70f93565fc994105d613a1361ce9d3c5` — **unverified on this host, file absent** |
| Feature schema | `football-1x2-features-0.3` |
| Code SHA (this eval branch) | `d72ff19afa60f088a890c599592ccdad1b6c3354` |
| Implementation audit SHA | `1cde8f701e2fcdfd85f9574983b76abd810003cc` |
| Walk-forward artefacts | not created |
| Candidate | not loaded, not retrained, not promoted |
| Calibration versions | not fit |
| Random seed | 42 (unused) |
| Odds fingerprint | not applicable (Evaluation A) |

---

## 6. Quality gates

Allowed: existence/hash check of the pinned parquet on this host. That check
**failed** (file missing; SHA not computed).

Forbidden and not done: Odds API, dataset regeneration, parquet modification,
retraining `football-elo-v1-candidate`, Value/AI Picks, ROI, EV, model
promotion.

Existing code-level PIT / calibration / OOS-helper tests (unmerged
`1cde8f7` worktree, 2026-09-12T18:31:28Z):

| Suite | Result |
| --- | --- |
| Value Engine / odds PIT | 34 passed, 2 skipped |
| ML provenance / OOS helpers / calibration / metrics / splits | 29 passed |
| AI Picks / Analyst grounding / frozen OOS | 33 passed |
| production-oos-sql / prematch | 18 passed, 1 skipped |
| Ingestion PIT / ML dataset | 19 passed, 1 failed (`pyarrow` missing in ingestion venv export test — packaging, not leakage) |
| Dataset SHA on this host | FAIL (file absent) |

These tests do **not** replace Evaluation A. They did not load the pinned
parquet and did not score 2024–2026 walk-forward OOS.

---

## 7. Exact status block

```text
STATUS: BLOCKED
DATASET: UNAVAILABLE ON THIS HOST
PREDICTIONS: NOT RUN
LOGLOSS: NOT COMPUTED
BRIER: NOT COMPUTED
ACCURACY: NOT COMPUTED
ECE: NOT COMPUTED
LEAKAGE: NOT RUN
REPRODUCIBILITY: BLOCKED
BACKTEST TYPE: Evaluation A only (not executed)
ODDS API REQUESTS: 0
VALUE/AI PICKS: NOT RUN
MODEL PROMOTION: NOT PROMOTED
```

The model is not production. The model is not validated. No performance
claim is made.

**Required unblock:** copy the original file onto this evaluation host at
`workers/ingestion/var/football-1x2-history.parquet`, confirm SHA-256
`0a11a3712c30e4f37c0ac0a75e0e321b70f93565fc994105d613a1361ce9d3c5` **on this
host**, then re-run Evaluation A only. A hash measured on another machine is
not sufficient.
