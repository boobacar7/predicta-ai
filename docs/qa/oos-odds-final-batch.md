# OOS historical odds — final batch

Data collection only. The frozen production OOS backtest was **not** rerun.
This report measures matches with valid live PIT 1X2 odds. It does not count AI Picks, hit rate, or ROI.

## Universe

387 total OOS matches

## Before

matches with valid PIT odds: **114 / 387**
coverage %: **29.46%**

## After

matches with valid PIT odds: **181 / 387**
coverage %: **46.77%**

## New

newly covered matches: **67**
newly persisted snapshots: **5485**

## By competition

| Competition | OOS matches | covered before | covered after | coverage % |
| --- | ---: | ---: | ---: | ---: |
| mls | 139 | 13 | 80 | 57.55% |
| premier-league | 30 | 30 | 30 | 100.00% |
| la-liga | 41 | 12 | 12 | 29.27% |
| bundesliga | 18 | 7 | 7 | 38.89% |
| serie-a | 30 | 22 | 22 | 73.33% |
| ligue-1 | 27 | 24 | 24 | 88.89% |
| champions-league | 102 | 6 | 6 | 5.88% |

## Requests

planned: **25**
executed: **10**
skipped: **15** (Champions League qualification sport key absent from The Odds API catalog)
reused: **77**

Champions League qualifying was not fetched: The Odds API `/v4/sports` catalog does not currently list `soccer_uefa_champs_league_qualification`. Existing `soccer_uefa_champs_league` snapshots were not refetched. MLS franchise aliases already in `MLS_NAME_ALIASES` were applied to match keys and existing MLS raw payloads were replayed (0 historical credits).

## Credits

before: **17110**
consumed: **100**
after: **17010**

## Rejections

total events (new historical fetches): **141**
exact matches: **80**
aliases: **0**
unmatched (fetch events + replay snapshot quarantines): **3738**
false matches: **0**
identity rejections: **3738**
other reasons: **0**

Replay of 15 existing MLS payloads accepted **3862** snapshot records via existing franchise aliases. Unmatched Odds API names were not guessed (La Liga / Bundesliga / Serie A / remaining MLS suffixes / CL group-stage names stay quarantined). Paris FC isolation is unchanged (3 Ligue 1 matches).

## PIT

post-cutoff snapshots persisted: **176**
post-kickoff snapshots persisted: **176**
invalid snapshots selected: **0**

The 176 post-kickoff rows sit on **11 MLS matches** that also have valid pre-kickoff 1X2 snapshots. Frozen PIT selection (`available_at <= kickoff`) does **not** use them. Coverage **181 / 387** counts only pre-kickoff snapshots. Future persist runs skip `available_at > kickoff` for target matches.

## Isolation

live snapshots: **43280**
mock snapshots: **0**
orphan odds: **0**

## Idempotence

duplicate snapshot IDs: **0**
duplicate persistence attempts: **0** (replay used existing raw payload IDs; new snapshot IDs were inserted)

Raw provider payloads were not overwritten. Duplicate persistence kept the first canonical snapshot.

