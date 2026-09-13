# Historical Odds collection — finalized STOP

**Status: STOPPED**

The unverified full-historical-2024-2026 collection job is stopped.

No collector is running. No replacement job will be started. No additional paid
Odds API requests will be made from this work. Existing raw payloads, snapshots,
and ingestion metadata are unchanged.

Audited at 2026-09-12T15:12Z. Stop finalized at 2026-09-12T17:09Z.

Machine-readable copy: `workers/ml/reports/historical-2024-2026-collection-audit.json`.

---

## Authoritative verified state

Source: `origin/agent/data/final-oos-odds-batch` commit `1cde8f7`
(`workers/ml/reports/oos-odds-final-batch.json`). These figures are the last
verified persisted snapshot. They are not live Postgres reads from this VM.

| Item | Verified value |
| --- | ---: |
| Canonical matches | **7622** |
| Live odds snapshots | **43280** |
| Raw payloads | **203** |
| Valid pre-kickoff 1X2 OOS matches | **181 / 387 = 46.77%** |
| Last paid historical requests | **10** |
| Credits consumed by that paid batch (`sum(x-requests-last)`) | **100** |
| New canonical OOS matches from those 10 paid requests | **0** |
| Reused requests (free replay of existing keys) | **77** |
| Unmatched Odds API names (quarantined) | **3738** |
| Champions League qualification slots that cannot be mapped | **15** |
| Last verified `x-requests-remaining` | **17010** |

OOS universe is dataset 0.3, `2026-07-01T00:00:00Z` inclusive through
`2026-09-10T02:30:01Z` exclusive. Coverage counts canonical matches with a valid
pre-kickoff 1X2 snapshot. It does not count raw events or snapshot rows as
matches.

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

Year-split coverage for 2024, 2025, and full-year 2026 is **unavailable**.
Those figures are not inferred.

---

## Discarded unverified claims

The following are **not** facts. Do not use them for planning, credits, or
coverage:

- 637 / 1348 planned requests
- 436 new requests executed
- ~1114 PIT records
- ~4.8 hours remaining
- ~19 seconds/request
- 711 remaining requests
- 7110 remaining credits
- any hypothetical credit remaining derived from those numbers

---

## Live probe at stop

| Check | Result |
| --- | --- |
| Collector / ingestion process | none |
| PostgreSQL `:5432` | closed |
| `THE_ODDS_API_KEY` | absent — no live quota probe, no paid calls |
| Raw store `workers/ingestion/var` | absent on this VM |
| Paid Odds API requests this stop | **0** |
| Data deleted / rolled back / rewritten | **none** |
| Backtest / ROI | **not run** |

This VM never had the unverified 2024–2026 job. It also must not start one.

---

## Why remaining paid collection is stopped

The last verified paid batch consumed 100 credits and added 0 new canonical OOS
matches. The +67 MLS OOS matches in that report came from 0-credit replay of
already-stored raw payloads (`77` reused request keys).

Further paid historical requests are blocked by identity and catalog limits, not
by missing timestamps:

- 15 planned Champions League qualification slots cannot map because
  `soccer_uefa_champs_league_qualification` is absent from The Odds API catalog.
- 3738 unmatched Odds API names remain quarantined. Names are not guessed.
- Premier League, Ligue 1, La Liga, Bundesliga, Serie A, and Champions League
  coverage did not move after the last 10 paid MLS historical calls.

---

## Last verified Odds API headers

From `persist.fetches[].quota` on the same `1cde8f7` report. Each historical
call billed `x-requests-last = 10`. Probe remaining was 17110; last historical
remaining was 17010; `x-requests-used` moved 2900 → 2990.

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

Live remaining credits in this VM are unavailable (no API key). The last
verified remaining value is **17010**. It is not updated by this stop.

---

## Preserved

- All persisted raw payloads kept
- All persisted snapshots kept
- Ingestion metadata kept
- Idempotence preserved
- No rollback
- No mutation of existing raw payloads or snapshots

---

## Next step (separate decision)

Do not continue historical collection from this stop.

The next step is a **separate** decision about the walk-forward dataset and
backtest, based **only** on verified persisted data:

- 7622 canonical matches
- 43280 live odds snapshots
- 203 raw payloads
- 181/387 valid pre-kickoff 1X2 OOS matches

That decision is out of scope for this stop. Do not run
`production-oos-backtest` or `final-oos-evaluation` until that separate
decision is made.
