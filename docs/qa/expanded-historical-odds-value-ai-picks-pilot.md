# Expanded Historical Odds / Value / AI Picks Pilot

**Branche :** `agent/data/expand-historical-odds-pilot`  
**Modèle :** `football-elo-v1-candidate` — **non promu**  
**Value Engine :** `value-engine-0.1` — **formules non modifiées**  
**AI Picks :** `ai-picks-0.1` — seuils, ranking et exclusions **non modifiés**  
**Provider cotes :** The Odds API v4, endpoint **historical**, région `eu`, marché `h2h` → `1X2`  
**CLI persist :** `python -m predicta_ingestion expand-historical-odds-pilot` (**sans** `--dry-run`)  
**CLI scoring :** `python -m app.backtesting persisted-expanded` (0 crédit)  
**Verdict pipeline / dataset :** **GO WITH CONDITIONS**

Ce run **élargit** le premier pilote persisté (`docs/qa/historical-odds-value-ai-picks-pilot.md`,
17 matchs / 21 AI Picks) sans recréer d'architecture parallèle et sans optimiser
la stratégie.

**Performance descriptive sur l'échantillon étudié ; insuffisante pour conclure à une rentabilité future.**

La clé The Odds API est lue depuis `workers/ingestion/.env` (gitignoré). Elle
n'apparaît dans aucun log, fixture, rapport JSON, test ou fichier Git.

---

## 1. Executive Summary

Le pilote persisté du 21–24 août 2026 avait **17** matchs labellisés et **21**
AI Picks. L'analyse suivante (`docs/qa/value-ai-picks-pilot-analysis.md`)
concluait : pas d'anomalie moteur, **n trop petit**.

Ce run ajoute des journées PL + Ligue 1 déjà présentes dans Sportmonks, réutilise
les snapshots weekend déjà persistés, et score le même pipeline :

Historical Odds → PIT → `football-elo-v1-candidate` → `value-engine-0.1` →
`ai-picks-0.1` → résultats réels.

| Contrôle | Résultat |
| --- | --- |
| Fenêtres | 2026-05-01→05-25 (fetch) ; 2026-08-21→08-25 (**reuse, 0 fetch**) ; 2026-08-28→09-07 (fetch) |
| Ligues | Premier League + Ligue 1 uniquement |
| Requêtes historical this run | **33** (cap 40 ; pas de grille 5 minutes) |
| Crédits `x-requests-last` | **330** prévus / **330** consommés |
| `--dry-run` | **false** |
| Snapshots acceptés this run | **5087** (11 collisions idempotentes) |
| Raw payloads this run | **33** |
| Matchs SQL dans les fenêtres | **127** (dont 1 reporté, hors parquet) |
| Cibles scorées | **119** |
| Rejets identité scoring | **7** (6 Paris isolé ; 1 Rennes/PSG conservé) |
| AI Picks éligibles | **161** sélections / 119 matchs |
| PIT / anti-leakage / Value parity / AI Picks parity / reproductibilité | **PASS** |
| `stale_odds` | **0** (âge max PIT ≈ 6,16 h < 24 h) |
| ROI théorique AI Picks | **+8,34 %** (n = 161) |
| Candidat promu | **non** |

Le ROI AI Picks est **positif** sur cet échantillon. Cela ne prouve pas une
rentabilité future.

**Performance descriptive sur l'échantillon étudié ; insuffisante pour conclure à une rentabilité future.**

Aucun seuil modifié. Aucun HOME/AWAY flip. Aucun match créé depuis les cotes.
Le weekend des 17 matchs n'a **pas** été refetché.

---

## 2. Objective

Augmenter la **taille de l'échantillon** réel labellisé, pas le ROI.

Question que ce dataset doit permettre d'aborder **ensuite**, sans retuning :

> AI Picks 0.1 apporte-t-il une Value réelle par rapport au modèle Elo seul ?

Ce rapport **ne répond pas** à cette question par un « oui économique ». Il
établit que le pipeline élargi est propre, PIT-safe, reproductible, et que
MODEL / VALUE / AI PICKS restent trois univers distincts.

Cible : **100–200 matchs réels**. Obtenu : **119** matchs identity-matched,
terminés, avec prédiction, cotes PIT et résultat réel.

---

## 3. Scope

Strictement football, PL + Ligue 1, marché `h2h` / `1X2`, région `eu`.

| Contrôle | Valeur |
| --- | --- |
| Sport | football |
| Compétitions | Premier League, Ligue 1 |
| Marché | `h2h` → canonique `1X2` (HOME / DRAW / AWAY) |
| Région | `eu` |
| Cadence | 1 requête historical / ligue / jour de coup d'envoi |
| `as_of` | premier kickoff de ce jour-là (snapshot provider ≤ `as_of`) |
| `MAX_EXPAND_REQUESTS` | 40 (plafond 400 crédits documentés) |
| `MIN_SLOT_GAP` | 12 h (refuse une grille 5 minutes) |
| Modèle | `football-elo-v1-candidate` inchangé |
| Value | `value-engine-0.1` inchangé |
| AI Picks | `ai-picks-0.1` seuils inchangés |
| Matching | exact + aliases validés uniquement |
| Sink | `TargetMatchOddsSink` — les cotes ne créent jamais un match |

Hors périmètre : La Liga, Bundesliga, Serie A, Champions League, MLS, BTTS,
over/under, handicaps, corners, player props, saison complète, tuning, nouveau
modèle, promotion.

Mécanismes **réutilisés** (pas de fork) : `persist_historical_odds.py`,
The Odds API historical, identité Sportmonks, PIT store, Prediction Service,
Value Engine, AI Picks, scoring `persisted`.

---

## 4. Historical Window

Les fenêtres ont été **figées avant le scoring**. Elles n'ont pas été choisies
pour maximiser le ROI.

| Nom | Bornes UTC | Fetch | Rôle |
| --- | --- | --- | --- |
| `end-2025-26-may` | 2026-05-01 → 2026-05-25 | oui | fin de saison 2025-26 déjà dans Sportmonks |
| `persist-weekend-2026-08-21` | 2026-08-21 → 2026-08-25 | **non** | pilote initial, snapshots déjà en base |
| `2026-27-following-matchweeks` | 2026-08-28 → 2026-09-07 | oui | journées suivantes 2026-27 |

Chevauchement des partitions Elo **existantes** (non retouchées) :

- `FINAL_TRAIN_END` = 2026-01-01
- `calibration_select` = 2026-05-01 → 2026-07-01 → **mai est dans calibration_select**
- `final_test` commence 2026-07-01 → **août–septembre est dans test**

Ce n'est **pas** un split OOS unique. Mai et août–septembre ne doivent pas être
fusionnés comme une preuve de généralisation. Le modèle n'a pas été recalibré
sur cet élargissement.

Horloge de scoring : `2026-09-07T00:00:00Z`. Tous les matchs scorés sont
antérieurs (terminés).

---

## 5. API Usage

Estimation **avant** le live run : 33 slots × 10 crédits documentés = **330**.
Cap dur 40 requêtes / 400 crédits. Reliquat provider largement supérieur.
`stop_reason=null`. Weekend **non refetché**.

| Poste | Valeur |
| --- | ---: |
| Requêtes planifiées | 33 |
| Requêtes exécutées | 33 |
| Ligues | 13 Ligue 1 + 20 Premier League |
| Crédits prévus (`x-requests-last`) | **330** |
| Crédits `sum(x-requests-last)` | **330** |
| `x-requests-used` première réponse | 160 (`remaining` 19840) |
| `x-requests-used` dernière réponse | 720 (`remaining` 19280) |
| Δ `used` / `remaining` | **560** |
| Backfill 5 minutes | **0** |
| Nouvelles compétitions | **0** |
| `--dry-run` | false |
| `--estimate-only` | false |

Tous les `snapshot_timestamp` sont **≤ `as_of`**. Aucune interpolation.

Le runner facture ce run à **330** via `x-requests-last` (toujours 10). Les
compteurs cumulés `used`/`remaining` ont bougé de 560 (sauts de +10, +20, +30
et un +60). Causes possibles : autre consommateur de la même clé, retries
non reflétés dans `last`, ou comptabilité provider au-delà de `last`. Écart
**documenté**, pas masqué. Le cap 40 requêtes n'a pas été dépassé.

Les 7 requêtes du weekend (70 crédits, `used` final alors 150 / `remaining`
19850) ne sont **pas** rejouées ici.

Détail des 33 fetches : `as_of` = premier kickoff du jour ; snapshot provider
typiquement ~5 minutes avant. Events envelope 8–25 (journées suivantes
incluses dans l'enveloppe, filtrées au sink).

Raw payload ids this run : 33 enveloppes immuables
`raw_the-odds-api-odds-*` (liste dans
`workers/ingestion/var/expand-historical-odds-pilot.json`, gitignoré).

---

## 6. Match Universe

Défini **avant** le scoring, à partir de Sportmonks déjà en base.

| Grandeur | n |
| --- | ---: |
| Matchs SQL union des 3 fenêtres | 127 |
| dont reuse weekend | 19 |
| dont fetch | 108 |
| Parquet labellisé (terminé + résultat) | 126 |
| Reporté, hors parquet | 1 — Nantes vs Toulouse `19433450` (status `postponed`, 17 mai 19:00Z) |
| Identity-matched scorés | **119** |
| Identity rejected (ledger) | 7 |
| Avec cotes PIT 1X2 | 119 / 119 scorés |
| Prédictions Elo | 119 |
| Premier League / Ligue 1 scorés | 71 / 48 |
| Fenêtre mai / weekend / suivantes | 66 / 17 / 36 |
| Jours de coup d'envoi distincts | 26 |
| League-days scorés | 40 |

Issues réelles (119) : HOME 46, DRAW 36, AWAY 37.

Le match reporté n'est **pas** fabriqué ni forcé dans le backtest. Les 6
matchs Paris (`tm_football-sportmonks-4508`) existent en SQL mais restent hors
scoring (0 cote persistée — voir matching).

---

## 7. Identity Matching

Règle : event The Odds API → match Sportmonks **existant** → match canonique.
Clé naturelle exacte `football|home|away|kickoff`, puis aliases
`the-odds-api-team-aliases-v1`. Pas de fuzzy, pas de similarité, pas de LLM,
pas de flip HOME/AWAY.

This run (events observés dans les slots fetch, hors weekend refetch) :

| Grandeur | n |
| --- | ---: |
| Events uniques observés | 138 |
| Events dans les fenêtres fetch | 109 |
| Events hors fenêtre (skippés au sink) | 29 (28 match ids Sportmonks hors cible) |
| Exact matches | 102 |
| Alias matches | 0 |
| Faux matches | 0 |
| Events rejetés | 6 |
| Quarantaine `unmatched_odds_event` | 391 (books des events rejetés) |

Les 6 rejets ingestion :

1. Paris FC vs Brest (2026-05-03) — isolation Paris / Paris FC / PSG
2. Rennes vs Paris FC (2026-05-10)
3. Paris FC vs Paris Saint Germain (2026-05-17)
4. Paris FC vs Nice (2026-08-30)
5. Marseille vs Paris FC (2026-09-06)
6. Aston Villa vs Liverpool commence_at **2026-05-17T11:30Z** — Sportmonks a
   Villa vs Liverpool le **2026-05-15T19:00Z**. Kickoff différent → REJECT.
   Aucun match créé. Le match Sportmonks du 15 mai reste l'identité canonique.

Scoring (univers parquet, exclusions structurées) :

| Kind | n | Détail |
| --- | ---: | --- |
| `isolated_team` | 6 | club Sportmonks `4508` « Paris », distinct de Paris FC et PSG |
| `inverted_home_away` | 1 | Rennes vs PSG `19715631` — exclusion labellisée du 16 août **conservée** |

Paris isolé (0 snapshot) :

- Paris vs Brest (3 mai)
- Rennes vs Paris (10 mai)
- Paris vs PSG (17 mai)
- Troyes vs Paris (22 août, weekend)
- Paris vs Nice (30 août)
- Marseille vs Paris (6 sept.)

Rennes/PSG : comme au premier persist, l'orientation The Odds API **proche du
kickoff** matche Sportmonks ; les snapshots weekend restent en base. Le scoring
élargit **conserve** l'exclusion labellisée. Ce n'est pas un flip, ni une
suppression silencieuse.

---

## 8. Persisted Data

`--dry-run=false`. PostgreSQL + raw store. Snapshots historical **append-only**.

| Grandeur | n |
| --- | ---: |
| Snapshots acceptés this run | 5087 |
| Duplicates `ON CONFLICT DO NOTHING` | 11 |
| Snapshots identity this run | 5087 |
| Raw payloads | 33 |
| `data_mode` | `live` |
| `source` | `the-odds-api-v4` |
| Scoring `loaded_snapshots` | 9089 (union SQL, y compris weekend déjà persisté) |
| Dataset `snapshots` (après exclusions) | 9022 |

Chaque snapshot porte : provider, `provider_id`, `source`, `data_mode`,
`raw_payload_id`, `ingestion_run_id`, `collected_at`, `available_at`,
`event_at`, sélections HOME/DRAW/AWAY.

Idempotence : une deuxième passe identique ne duplique pas les ids canoniques
(tests + 11 collisions live déjà observées). Le weekend n'a pas été réécrit
par un refetch.

Les champs persist hérités `expected_target_matches=17` /
`expected_window_matches=19` viennent du runner weekend **réutilisé**. La
source de vérité de l'univers élargi est `estimate` (127 / 108 fetch / 19 reuse),
pas ces deux constantes.

---

## 9. PIT

**PASS**

Couches **non modifiées** :

1. **Cotes Value / OddsService** : `available_at <= kickoff`. `event_at`
   identifie le match ; il n'exclut pas les cotes pre-match du match cible.
2. **Features ML / PointInTimeStore** : `event_at < cutoff` et
   `available_at < cutoff`. Cutoff post-kickoff → `DataLeakageError` /
   `TemporalLeakageError`.

Spot-check runner (Nantes vs Marseille, T = 2026-05-02T13:00Z) :
`selected_available_at=2026-05-02T12:55:31Z`, `before_eligible=true`,
`after_excluded=true`, `leaked=false`.

Politique bookmaker (Value 0.1, inchangée) :

> Last complete 1X2 snapshot with `available_at <= cutoff`, ordered by
> `(available_at, collected_at, snapshot.id)`. Bookmaker identity is not a
> selection criterion; Pinnacle is not preferred because it looks better.

Âge PIT sur les 119 cibles : min **0,07 h**, moyenne **1,44 h**, max **6,16 h**.
Aucun snapshot post-kickoff retenu. Aucun `stale_odds` (seuil 24 h **non**
relâché).

---

## 10. Anti-Leakage

**PASS**

| Contrôle | Résultat |
| --- | --- |
| Snapshot `available_at` ≤ kickoff | oui, 119/119 |
| Snapshot après kickoff refusé | tests ingestion + API |
| Snapshot disponible après cutoff | PIT `<` ; Value `<=` kickoff |
| Features post-kickoff | `DataLeakageError` / `TemporalLeakageError` |
| HOME/AWAY non retournés | Paris FC unmatched ; Villa/Liverpool kickoff mismatch unmatched |
| Cotes hors fenêtre | 29 events observés, skippés au sink |
| Résultat réel | lu seulement au settlement |
| Nantes–Toulouse reporté | hors parquet, hors scoring |
| Matchs futurs | aucun dans le backtest (horloge 7 sept.) |

Les labels parquet `target` ne sont pas des features Elo. Le snapshot n'est
**pas** choisi rétroactivement selon le ROI.

---

## 11. Prediction

`football-elo-v1-candidate` exclusivement. K, home advantage, dataset, schema,
calibration, registry et code modèle **inchangés**. `model_status=candidate`.
Non promu. Pas d'XGBoost, pas de LightGBM, pas d'ensemble.

119 prédictions. Features parquet `home_elo_pre` / `away_elo_pre` / `elo_diff`
au cutoff kickoff.

Argmax : **93 HOME / 0 DRAW / 26 AWAY**.

---

## 12. Odds

Uniquement `the-odds-api-v4`, `1X2`, `eu`. 26 books observés this run.

Books retenus au cutoff (last-complete, **pas** le meilleur EV) parmi les 119 :

winamax_fr 26, betsson 21, winamax_de 12, betclic_fr 10, coolbet 9, unibet_nl 7,
pinnacle 6, unibet_fr 6, unibet_se 4, betfair_ex_eu 4, williamhill 3, nordicbet 2,
matchbook 2, tipico_de 2, onexbet 2, gtbets 2, everygame 1.

Pinnacle n'est pas préféré. `maximum_odds_age=24h` inchangé.

---

## 13. Value Engine

**PASS** — parité live (`value_parity.errors` vide).

Formules **exclusives**, version `value-engine-0.1` :

```
implied_probability = 1 / odds
overround = Σ implied_probability
no_vig_probability = implied_probability / overround
edge = model_probability - implied_probability
EV = model_probability × odds - 1
```

Aucune seconde Value Engine. Aucune formule parallèle dans le scoring élargi.

---

## 14. AI Picks

Moteur `AiPicksEngine` existant. Pas de second ranking.

- Score : `opportunity_score = EV + Edge`
- Tri : score, EV, edge, fraîcheur, `match_id`, sélection
- Seuils V0.1 : `min_edge=0`, `min_ev=0`, `min_p=0`, `max_odds_age=24h`
- `optimized_on_test=false`

161 opportunités éligibles. Plusieurs sélections possibles par match.
Paris isolé et Rennes/PSG **absents** du ranking.

Compte fermé : 119 × 3 = 357 issues. 161 picks + 196 `negative_ev` = 357.
`stale_odds=0`, `invalid_odds=0`. Rien n'est supprimé silencieusement.

**Convention ROI :** 1 unité par opportunité / pick
(`fixed_unit_per_opportunity`). Un match à 2 AI Picks contribue **2** unités
au dénominateur. Ce n'est pas un ROI par match.

---

## 15. Model Performance

Univers **distinct** de Value et d'AI Picks. Argmax Elo. **Pas un ROI.**

| Métrique | Valeur |
| --- | --- |
| n | 119 |
| Hits | 54 |
| Accuracy | 45,38 % |
| Log Loss | 1,048 |
| Brier | 0,630 |
| ECE | 0,048 |
| Argmax HOME / DRAW / AWAY | 93 / 0 / 26 |

| Ligue | n | Accuracy | Log Loss | Brier | ECE |
| --- | ---: | ---: | ---: | ---: | ---: |
| Premier League | 71 | 46,48 % | 1,020 | 0,608 | 0,108 |
| Ligue 1 | 48 | 43,75 % | 1,090 | 0,662 | 0,110 |

Matrice de confusion (lignes = réel HOME/DRAW/AWAY, colonnes = prédit) :

|  | pred HOME | pred DRAW | pred AWAY |
| --- | ---: | ---: | ---: |
| réel HOME | 41 | 0 | 5 |
| réel DRAW | 28 | 0 | 8 |
| réel AWAY | 24 | 0 | 13 |

Le modèle ne prédit **aucun** DRAW (rappel DRAW = 0). Recall HOME = 89,1 % ;
precision HOME = 44,1 %. Support : HOME 46, DRAW 36, AWAY 37.

Note moteur : « Model argmax accuracy on identity-matched matches. Not a
betting ROI. »

---

## 16. Value Performance

Elo argmax **settled** sur la cote PIT (une ligne par match, sans filtre
EV/edge). Ce n'est **pas** le ranking AI Picks.

| Métrique | Valeur |
| --- | --- |
| n (opportunités = matchs) | 119 |
| Hits | 54 |
| Hit rate | 45,38 % |
| Cote moyenne | 2,07 |
| Edge moyen | −0,061 |
| EV moyen | −0,060 |
| Profit théorique | −15,57 u |
| ROI théorique | **−13,08 %** |
| Drawdown max | 19,20 u / 16,1 % du stake cumulé |
| HOME / AWAY | 93 / 26 |

| Sous-ensemble | n | Hits | ROI théorique |
| --- | ---: | ---: | ---: |
| Ligue 1 | 48 | 21 | −14,33 % |
| Premier League | 71 | 33 | −12,24 % |
| HOME | 93 | 41 | −13,97 % |
| AWAY | 26 | 13 | −9,92 % (n < 30, warning échantillon) |

Baseline naive HOME, **même** 119 matchs : hit rate 38,66 %, ROI **−14,55 %**,
profit −17,32 u, drawdown 24,95 u / 21,0 %.

---

## 17. AI Picks Performance

Produit `ai-picks-0.1`, une ligne par sélection éligible. Mise 1 u / pick.

| Métrique | Valeur |
| --- | --- |
| n | 161 |
| Hits | 41 |
| Hit rate | 25,47 % |
| HOME / DRAW / AWAY | 55 / 54 / 52 |
| Cote moyenne | 4,99 |
| Edge moyen | +0,060 |
| EV moyen | +0,335 |
| Profit théorique | +13,43 u |
| ROI théorique | **+8,34 %** |
| Drawdown max | 15,00 u / 9,32 % du stake cumulé |
| Picks / match (119 éligibles) | 1,35 |

EV moyen positif et hit rate ~25 % coexistent : le ranking favorise des cotes
plus longues que l'argmax (4,99 vs 2,07). n = 161 dépasse le seuil interne
d'échantillon insuffisant (30) mais **ne constitue pas** une preuve OOS de
rentabilité. Mai recouvre `calibration_select`.

**Performance descriptive sur l'échantillon étudié ; insuffisante pour conclure à une rentabilité future.**

Aucun langage de garantie. Aucune optimisation de seuil a posteriori. La
tranche « meilleure » ci-dessous n'est **pas** une nouvelle stratégie.

---

## 18. HOME / DRAW / AWAY

Issues réelles (119 matchs) : 46 HOME, 36 DRAW, 37 AWAY.

| Stratégie | HOME | DRAW | AWAY | Hit rate | ROI |
| --- | ---: | ---: | ---: | ---: | ---: |
| Elo argmax | 93 | 0 | 26 | 45,38 % | n/a (modèle) |
| Value argmax settled | 93 | 0 | 26 | 45,38 % | −13,08 % |
| Naive HOME | 119 | 0 | 0 | 38,66 % | −14,55 % |
| AI Picks | 55 | 54 | 52 | 25,47 % | +8,34 % |

AI Picks par sélection (1 u / pick) :

| Sélection | n | Hits | Hit rate | ROI théorique |
| --- | ---: | ---: | ---: | ---: |
| HOME | 55 | 15 | 27,27 % | −9,47 % |
| DRAW | 54 | 12 | 22,22 % | +2,85 % |
| AWAY | 52 | 14 | 26,92 % | +32,88 % |

Les ROI par sélection sont **descriptifs**. On ne retient pas AWAY a posteriori.

---

## 19. Competition Breakdown

|  | Premier League | Ligue 1 |
| --- | ---: | ---: |
| Matchs scorés | 71 | 48 |
| Accuracy Elo | 46,48 % | 43,75 % |
| Value ROI (argmax settled) | −12,24 % | −14,33 % |
| Naive HOME ROI | −4,41 % | −29,56 % |
| AI Picks n | 97 | 64 |
| AI Picks hits | 26 | 15 |
| AI Picks hit rate | 26,80 % | 23,44 % |
| AI Picks ROI | +5,30 % | +12,95 % |

Les deux ligues sont dans l'univers comparable du premier pilote. Pas de
compétition ajoutée pour « chercher du ROI ».

---

## 20. Odds / Edge / EV Analysis

Tranches **descriptives uniquement**. Ne pas sélectionner rétroactivement la
meilleure. `note=descriptive_only`.

### Odds (AI Picks)

| Tranche | n | Hits | Hit rate | ROI |
| --- | ---: | ---: | ---: | ---: |
| < 1.50 | 0 | — | — | — |
| 1.50–2 | 2 | 2 | 100 % | +79,0 % |
| 2–3 | 26 | 9 | 34,6 % | −14,1 % |
| 3–5 | 77 | 21 | 27,3 % | +11,3 % |
| > 5 | 56 | 9 | 16,1 % | +12,2 % |

### Edge

| Tranche | n | Hits | Hit rate | ROI |
| --- | ---: | ---: | ---: | ---: |
| < 5 % | 70 | 22 | 31,4 % | +15,8 % |
| 5–10 % | 66 | 13 | 19,7 % | −8,7 % |
| 10–20 % | 24 | 5 | 20,8 % | −0,4 % |
| 20–30 % | 1 | 1 | 100 % | +820 % |
| > 30 % | 0 | — | — | — |

### EV

| Tranche | n | Hits | Hit rate | ROI |
| --- | ---: | ---: | ---: | ---: |
| 0–0.15 | 56 | 20 | 35,7 % | +16,0 % |
| 0.15–0.40 | 56 | 9 | 16,1 % | −31,0 % |
| 0.40–1.00 | 41 | 10 | 24,4 % | +31,4 % |
| ≥ 1.00 | 8 | 2 | 25,0 % | +112,5 % |

### Probabilité modèle

| Tranche | n | Hits | Hit rate | ROI |
| --- | ---: | ---: | ---: | ---: |
| < 20 % | 13 | 2 | 15,4 % | +21,2 % |
| 20–30 % | 86 | 19 | 22,1 % | +9,3 % |
| 30–40 % | 33 | 8 | 24,2 % | +3,4 % |
| 40–50 % | 23 | 9 | 39,1 % | +7,7 % |
| > 50 % | 6 | 3 | 50,0 % | −4,5 % |

### Âge des cotes

| Tranche | n | Hits | Hit rate | ROI |
| --- | ---: | ---: | ---: | ---: |
| < 0.25 h | 97 | 25 | 25,8 % | +16,8 % |
| 0.25–2 h | 2 | 1 | 50,0 % | +14,5 % |
| 2–4 h | 48 | 11 | 22,9 % | −2,9 % |
| 4–24 h | 14 | 4 | 28,6 % | −12,3 % |
| ≥ 24 h | 0 | — | — | — |

Les cellules à n très petit (1.50–2, edge 20–30 %, âge 0.25–2 h) sont du
bruit. Elles ne justifient aucun changement de seuil.

---

## 21. Multiple Picks Analysis

Comportement AI Picks 0.1 **inchangé**. Au plus une ligne par
match / marché / sélection ; plusieurs issues du même match peuvent passer
`EV ≥ 0`.

| Matchs avec | n |
| --- | ---: |
| 0 pick | 7 |
| 1 pick | 63 |
| 2 picks | 49 |
| 3 picks | 0 |
| Total matchs éligibles | 119 |
| Total picks | 161 = 0×7 + 1×63 + 2×49 |

**ROI = 1 unité par pick**, pas par match. Un match à 2 picks = 2 u de
stake. Documenté dans `stake_note` du JSON de scoring.

---

## 22. Drawdown

Settlement théorique, mise fixe 1 u, ordre chronologique des opportunités,
pas de commission.

| Stratégie | n | Profit | ROI | DD max (u) | DD / stake cumulé |
| --- | ---: | ---: | ---: | ---: | ---: |
| Value argmax settled | 119 | −15,57 | −13,08 % | 19,20 | 16,1 % |
| Naive HOME | 119 | −17,32 | −14,55 % | 24,95 | 21,0 % |
| AI Picks | 161 | +13,43 | +8,34 % | 15,00 | 9,32 % |

Le drawdown AI Picks plus bas n'est **pas** une preuve de robustesse. Variance
de longs cotes + n limité + mélange calibration_select / test.

---

## 23. Reproducibility

**PASS**

Deux évaluations scoring, mêmes snapshots SQL, même artefact candidate, même
horloge `2026-09-07T00:00:00Z` : fingerprint prédictions / books / picks / ROI
identique.

Le scoring **n'appelle pas** The Odds API. Relancer
`python -m app.backtesting persisted-expanded` reconstruit le dataset sans
crédit.

Ingestion : ids canoniques stables ; 11 duplicates live confirment
`ON CONFLICT DO NOTHING`. CI : live-off, fixtures, clé de test seulement.

JSON QA gitignorés (`var/`) :

- `workers/ingestion/var/expand-historical-odds-pilot.json`
- `workers/ingestion/var/persisted-expanded-score.json`

Dataset analytique : 378 lignes (126 matchs parquet × 3 sélections), y compris
les 7 exclusions labellisées. Colonnes minimales : `match_id`, `competition`,
`kickoff_at`, `home_team`, `away_team`, `result`, `prediction`,
`model_probability`, `odds`, `bookmaker` / `provider`, `snapshot_at`,
`odds_age`, `implied_probability`, `no_vig_probability`, `edge`, `EV`,
`AI_Pick_eligibility`, `selection`, `rank`, `model_version`,
`value_engine_version`, `ai_picks_version`, `cutoff_at`, `data_mode`.

---

## 24. Limitations

1. n = 119 matchs / 161 picks : plus informatif que 17/21, **insuffisant**
   pour conclure à une rentabilité future.
2. Mai recouvre `calibration_select` Elo ; août–septembre recouvre `final_test`.
   Ce n'est pas un unique hold-out.
3. Rennes/PSG : snapshots weekend persistés ; scoring conserve l'exclusion
   labellisée du 16 août.
4. 6 matchs du club Sportmonks « Paris » (`4508`) sans cotes (Paris FC unmatched).
5. Event The Odds API Villa–Liverpool au 17 mai vs Sportmonks au 15 mai :
   reject kickoff, pas de création de match.
6. Last-complete peut retenir un book autre que Pinnacle.
7. 1X2 uniquement.
8. Elo never-DRAW (0 argmax DRAW / 119).
9. Δ `x-requests-used` 560 vs 330 `x-requests-last` : comptabilité provider /
   concurrence possible, non masquée.
10. PIT ingestion (`<` cutoff) et Value (`<=` kickoff) restent deux contrats.
11. Tranches odds/edge/EV/âge : analyse, pas une grille de filtres futurs.

---

## 25. Findings

1. **La puissance statistique a augmenté** : 17 → **119** matchs labellisés
   propres, 21 → **161** AI Picks, plusieurs journées, PL + Ligue 1.
2. Le pipeline Odds → PIT → Elo candidate → Value 0.1 → AI Picks 0.1 **tient**
   à cette échelle : PIT, anti-leakage, parités, reproductibilité PASS.
3. MODEL ≠ VALUE ≠ AI PICKS. Elo argmax 45,4 % n'est pas le hit rate AI Picks
   25,5 %. Value settled ROI −13,1 % n'est pas le ROI AI Picks +8,3 %.
4. AI Picks reste une stratégie de **cotes plus longues** (moyenne 4,99) et de
   multi-picks (49 matchs à 2 sélections). Convention : 1 u / pick.
5. Un ROI AI Picks positif sur cet échantillon **ne valide pas** la stratégie.
   Naive HOME et Value argmax sont négatifs sur les **mêmes** 119 matchs ; cela
   n'invalide pas non plus AI Picks.
6. Identité : Paris FC / Paris / PSG restent isolés. Pas de flip. Un mismatch
   de kickoff Villa–Liverpool a été rejeté, pas « corrigé ».
7. Coût : 33 requêtes, 330 crédits `last`, weekend réutilisé. Qualité > course
   aux 200 matchs.

---

## 26. Verdict

Le verdict porte sur la **qualité du dataset / pipeline**, pas sur la
rentabilité.

| Gate | Résultat |
| --- | --- |
| ≥ ~100 matchs réels propres | **PASS** (119) |
| PL + Ligue 1, plusieurs journées | **PASS** (26 dates) |
| Résultats réels, pas de score fabriqué | **PASS** |
| Odds historical réelles persistées | **PASS** (5087 this run + weekend reuse) |
| Provenance complète | **PASS** |
| Identité correcte, pas de match inventé | **PASS** |
| Aucun HOME/AWAY flip | **PASS** |
| PIT | **PASS** |
| Anti-leakage | **PASS** |
| Value parity | **PASS** |
| AI Picks parity | **PASS** |
| Reproductibilité | **PASS** |
| Modèle / seuils inchangés | **PASS** |
| Pas d'optimisation de ROI | **PASS** |
| Weekend 17 matchs non refetché | **PASS** |
| Secrets absents du git | **PASS** |
| `stale_odds` artificiel | **évité** (âge < 24 h) |

**GO WITH CONDITIONS**

GO ne signifie pas « AI Picks rentable ». Le ROI théorique AI Picks est
positif sur **cet** échantillon. Le constat économique reste :

**Performance descriptive sur l'échantillon étudié ; insuffisante pour conclure à une rentabilité future.**

Conditions :

1. `football-elo-v1-candidate` reste candidate — pas de promotion.
2. Value Engine 0.1 et AI Picks 0.1 restent inchangés (pas de tuning, pas de
   meilleure tranche).
3. Ne pas présenter n = 119 / 161 comme une preuve de ROI futur.
4. Séparer mai (`calibration_select`) et août–septembre (`final_test`) avant
   toute conclusion OOS.
5. Conservé : Paris isolé ; Rennes/PSG hors univers scoring.
6. CI live-off. Pas de grille 5 minutes. Budget crédits explicite.
7. Documenter `x-requests-last` (330) et Δ `used` (560) sans les confondre.

**NO-GO évité** : persistance réelle, PIT, anti-leakage, parité, pas de flip,
pas de secret, pas de promotion, cible ~100 atteinte sans backfill massif.

Quality gates locales (`.venv` de chaque package ; `python` n'est pas sur le
PATH système). CI live-off. OpenAPI inchangé. Aucun secret. Aucune promotion.
`verify:all` = concaténation des quatre gates Python/web ; toutes **PASS**.

| Commande | Résultat |
| --- | --- |
| `verify:ingestion` | ruff + mypy + **167 passed** |
| `verify:api` | ruff + mypy + **588 passed** |
| `verify:ml` | ruff + mypy + **29 passed** |
| `verify:web` / `verify:openapi` | openapi + typecheck + lint + **283 passed** + build |
| `verify:all` | **PASS** (les quatre gates ci-dessus via `.venv`) |

---

## 27. Next Steps

1. Laisser le candidat **non promu**.
2. Ne pas tuner `minimum_edge` / `maximum_odds_age` / ranking sur ce dataset.
3. Toute question « AI Picks vs Elo seul » doit comparer les **trois** univers
   (modèle, value settled, picks) et, si possible, mai vs août–septembre
   séparément — sans changer les règles.
4. Dossier identité dédié : Paris (`4508`) vs Paris FC ; Rennes/PSG orientation
   temporelle ; Villa–Liverpool kickoff Odds vs Sportmonks. Pas de flip.
5. Si un nouvel élargissement : même cadence 1 snapshot / ligue / jour, skip
   des league-days déjà persistés, cap crédits, arrêt propre.
6. Ne pas chercher la fenêtre, le book ou le snapshot qui rend le ROI plus
   joli.

---

## Commandes

```bash
# Estimation 0 crédit
cd workers/ingestion
python -m predicta_ingestion expand-historical-odds-pilot --estimate-only

# Persist borné (live, crédits réels, pas --dry-run)
python -m predicta_ingestion expand-historical-odds-pilot

# Scoring 0 crédit (SQL + parquet, pas d'appel The Odds API)
cd apps/api
python -m app.backtesting persisted-expanded
```

Tests déterministes : `workers/ingestion/tests/test_expand_historical_odds_pilot.py`,
`apps/api/tests/test_expand_historical_odds_scoring.py`. Aucun test unitaire
n'appelle The Odds API.
