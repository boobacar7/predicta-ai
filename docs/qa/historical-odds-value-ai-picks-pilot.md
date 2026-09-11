# Historical Odds → Value → AI Picks — premier run persisté

**Branche :** `agent/data/persist-historical-odds-pilot`  
**Modèle :** `football-elo-v1-candidate` — **non promu**  
**Value Engine :** `value-engine-0.1` — **formules non modifiées**  
**AI Picks :** `ai-picks-0.1` — seuils, ranking et exclusions **non modifiés**  
**Provider cotes :** The Odds API v4, endpoint **historical**, région `eu`, marché `h2h` → `1X2`  
**CLI persist :** `python -m predicta_ingestion persist-historical-odds-pilot` (**sans** `--dry-run`)  
**CLI scoring :** `python -m app.backtesting persisted-weekend` (0 crédit)  
**Verdict :** **GO WITH CONDITIONS**

Ce run persiste un univers historical **borné** pour les 17 matchs PL + Ligue 1
déjà labellisés (21–24 août 2026), puis mesure :

Historical Odds → PIT → football-elo-v1-candidate → value-engine-0.1 →
ai-picks-0.1 → résultats réels → métriques descriptives.

Il **ne** prouve **pas** qu'AI Picks est rentable.

**Résultat descriptif, insuffisant pour conclure à une rentabilité future.**

La clé The Odds API est lue depuis `workers/ingestion/.env` (gitignoré). Elle
n'apparaît dans aucun log, fixture, rapport JSON, test ou fichier Git.

---

## 1. Executive Summary

Le pilote Value / AI Picks précédent (`docs/qa/value-ai-picks-backtest-pilot.md`)
avait 17 prédictions Elo réelles et **0 cote persistée** (756 snapshots
observés en `--dry-run` au 16 août). AI Picks réel était impossible.

Ce run :

| Contrôle | Résultat |
| --- | --- |
| Fenêtre | `2026-08-21T00:00Z` → `2026-08-25T00:00Z` |
| Ligues | Premier League + Ligue 1 uniquement |
| Requêtes historical | **7** (cap 8 ; pas de 5 minutes) |
| Crédits | **70** (`x-requests-last=10` chacune) |
| `--dry-run` | **false** |
| Snapshots persistés (weekend) | **1011** |
| Raw payloads | **7** enveloppes immuables |
| Matchs SQL fenêtre | **19** |
| Cibles scorées | **17** |
| Rejets identité scoring | **2** (Paris FC isolé ; Rennes/PSG conservé) |
| PIT / anti-leakage / Value parity / AI Picks parity / reproductibilité | **PASS** |
| `stale_odds` | **0** (âge max observé ≈ 5,08 h < 24 h) |
| AI Picks éligibles | **21** sélections / 17 matchs |
| ROI théorique AI Picks | **−32,3 %** (n = 21) |
| Candidat promu | **non** |

Aucun backfill. Aucune saison supplémentaire. Aucun match créé depuis les
cotes. Aucun retournement HOME/AWAY. Aucun seuil modifié.

---

## 2. Scope

Strictement :

| Contrôle | Valeur |
| --- | --- |
| Sport | football |
| Marché | `h2h` / canonique `1X2` |
| Région | `eu` |
| Ligues | `premier-league`, `ligue-1` |
| Fenêtre coups d'envoi | 21–24 août 2026 |
| Cadence | 1 requête historical / ligue / jour de coup d'envoi |
| `as_of` | premier kickoff de ce jour-là (snapshot provider ≤ `as_of`) |
| `MAX_PERSIST_REQUESTS` | 8 |
| `MIN_SLOT_GAP` | 12 h (refuse une grille 5 minutes) |
| Schéma | Alembic `0004_odds_history` (aucune migration nouvelle) |

Hors périmètre : La Liga, Bundesliga, Serie A, Champions League, MLS, BTTS,
over/under, handicaps, corners, player props, backfill multi-saisons.

---

## 3. Matchs ciblés

19 matchs Sportmonks déjà en base. Les 17 cibles sont ceux **déjà matchés**
lors du pilote odds du 16 août. Les 2 identités exclues restent hors scoring.

| Coup d'envoi (UTC) | Ligue | Match | Sportmonks | Scoring |
| --- | --- | --- | --- | --- |
| 2026-08-21 18:45 | Ligue 1 | Olympique Marseille vs Strasbourg | `19715633` | cible |
| 2026-08-21 19:00 | Premier League | Arsenal vs Coventry City | `19722203` | cible |
| 2026-08-22 11:30 | Premier League | Hull City vs Manchester United | `19722202` | cible |
| 2026-08-22 14:00 | Premier League | Nottingham Forest vs Leeds United | `19722199` | cible |
| 2026-08-22 14:00 | Premier League | Ipswich Town vs Sunderland | `19722200` | cible |
| 2026-08-22 14:00 | Premier League | Everton vs Crystal Palace | `19722201` | cible |
| 2026-08-22 15:15 | Ligue 1 | Lens vs Auxerre | `19715634` | cible |
| 2026-08-22 16:30 | Premier League | Brentford vs Tottenham Hotspur | `19722198` | cible |
| 2026-08-22 18:45 | Ligue 1 | Troyes vs Paris | `19715629` | **rejet isolé** |
| 2026-08-22 18:45 | Ligue 1 | Toulouse vs Olympique Lyonnais | `19715630` | cible |
| 2026-08-22 18:45 | Ligue 1 | Nice vs Lorient | `19715632` | cible |
| 2026-08-22 18:45 | Ligue 1 | Le Mans vs Brest | `19715635` | cible |
| 2026-08-23 13:00 | Ligue 1 | Angers SCO vs LOSC Lille | `19715637` | cible |
| 2026-08-23 13:00 | Premier League | Manchester City vs AFC Bournemouth | `19722196` | cible |
| 2026-08-23 13:00 | Premier League | Brighton & Hove Albion vs Aston Villa | `19722197` | cible |
| 2026-08-23 15:15 | Ligue 1 | Le Havre vs Monaco | `19715636` | cible |
| 2026-08-23 15:30 | Premier League | Newcastle United vs Liverpool | `19722195` | cible |
| 2026-08-23 18:45 | Ligue 1 | Rennes vs Paris Saint Germain | `19715631` | **rejet identité conservé** |
| 2026-08-24 19:00 | Premier League | Fulham vs Chelsea | `19722194` | cible |

Aucun match n'a été ajouté ou retiré pour améliorer le ROI.

---

## 4. Matching

Règles **inchangées** : clé naturelle exacte `football|home|away|kickoff`,
puis aliases explicites `the-odds-api-team-aliases-v1`. Pas de fuzzy, pas de
similarité, pas de LLM. Les cotes ne créent jamais un match canonique.

| Grandeur | n |
| --- | ---: |
| Events The Odds API uniques observés | 39 |
| Events dans la fenêtre | 19 |
| Events hors fenêtre (journées suivantes, skippés) | 20 |
| Exact matches ingestion (fenêtre) | 18 |
| Alias matches | 0 |
| Faux matches | 0 |
| Events rejetés ingestion | 1 (Troyes vs Paris FC) |
| Univers scoring | 17 cibles + 2 exclusions labellisées |

### Paris FC — toujours rejeté

Event `Troyes vs Paris FC` (`2026-08-22T18:45Z`). Sportmonks : Troyes vs
**Paris** (`tm_football-sportmonks-4508`). Isolation Paris / Paris FC / PSG.
Aucune alias. Quarantaine `unmatched_odds_event`. **0** snapshot persisté sur
`mth_football-sportmonks-19715629`.

### Rennes / PSG — orientation provider au cutoff vs labellisation du 16 août

Au pilote odds du **16 août**, The Odds API publiait `Paris Saint Germain vs
Rennes` alors que Sportmonks est `Rennes vs Paris Saint Germain`. Rejet
`inverted_home_away` correct : on ne retourne pas HOME/AWAY.

Aux timestamps persistés **proches du coup d'envoi** (21–23 août), le même
event The Odds API est `Rennes vs Paris Saint Germain`. L'identité exacte
matche. **Aucun retournement HOME/AWAY n'a été appliqué.** 67 snapshots ont
été append-only persistés sur `mth_football-sportmonks-19715631`.

Pour **ce** pilote de scoring, l'exclusion labellisée
`WEEKEND_IDENTITY_EXCLUSIONS` est conservée : Rennes/PSG n'entre pas dans
les 17 cibles Value / AI Picks. Les snapshots existent en base ; ils ne sont
pas utilisés pour le ranking. Ce n'est pas une suppression silencieuse : le
rejet est structuré (`inverted_home_away` dans le ledger qualité).

Les 20 events hors fenêtre (journée PL suivante visible au snapshot du 24
août) ont été **skippés** (`TargetMatchOddsSink`). Pas de match inventé.

---

## 5. API requests

7 slots planifiés, 7 exécutés, `stop_reason=null`.

| # | Ligue | `as_of` demandé | `snapshot_timestamp` | Events envelope | `x-requests-last` | `requests_used` | `requests_remaining` |
| ---: | --- | --- | --- | ---: | ---: | ---: | ---: |
| 1 | ligue-1 | 2026-08-21T18:45Z | 2026-08-21T18:40:38Z | 9 | 10 | 90 | 19910 |
| 2 | ligue-1 | 2026-08-22T15:15Z | 2026-08-22T15:10:38Z | 8 | 10 | 100 | 19900 |
| 3 | ligue-1 | 2026-08-23T13:00Z | 2026-08-23T12:55:38Z | 3 | 10 | 110 | 19890 |
| 4 | premier-league | 2026-08-21T19:00Z | 2026-08-21T18:55:38Z | 15 | 10 | 120 | 19880 |
| 5 | premier-league | 2026-08-22T11:30Z | 2026-08-22T11:25:38Z | 14 | 10 | 130 | 19870 |
| 6 | premier-league | 2026-08-23T13:00Z | 2026-08-23T12:55:38Z | 14 | 10 | 140 | 19860 |
| 7 | premier-league | 2026-08-24T19:00Z | 2026-08-24T18:55:38Z | 21 | 10 | 150 | 19850 |

Pas de slot Ligue 1 le 24 août (aucun coup d'envoi L1 ce jour-là). 7 < 8 :
le cap n'a pas été saturé. Aucun snapshot interpolé (`snapshot_timestamp`
toujours ≤ `as_of`).

---

## 6. Crédits consommés

Mesure réelle (headers provider). Aucune hypothèse.

| Poste | Valeur |
| --- | ---: |
| Requêtes this run | 7 |
| Crédits this run | **70** |
| Crédit / requête | 10 |
| `requests_used` fin | 150 |
| `requests_remaining` fin | 19850 |
| Backfill 5 minutes | **0** |
| Nouvelles compétitions | **0** |

Le runner s'arrête si le reliquat ne couvre plus les slots restants, ou si
`x-requests-last > 10`. Ici le reliquat suffisait ; pas d'arrêt anticipé.

---

## 7. Snapshots observés

Chaque fetch historical renvoie **tous** les events de la ligue au timestamp
demandé, y compris des journées suivantes. 39 events uniques observés, dont
19 dans la fenêtre.

Les books des events rejetés / hors cible ne sont pas inventés comme matchs.
46 quarantaines `unmatched_odds_event` = books de Troyes–Paris FC sur les
deux snapshots Ligue 1 où l'event est encore listé (21 et 22 août).

---

## 8. Snapshots persistés

`--dry-run=false`. Écriture réelle PostgreSQL + raw store.

| Grandeur | n |
| --- | ---: |
| Snapshots canonical weekend | **1011** |
| dont 17 cibles (scoring) | **944** |
| dont Rennes/PSG persistés hors scoring | **67** |
| dont Paris FC | **0** |
| `data_mode` | `live` |
| `source` | `the-odds-api-v4` |
| `available_at == collected_at` canonique | `last_update` bookmaker |
| Raw payload ids | 7 (ci-dessous) |

`ingestion_run_id` :
`ing_the-odds-api-2026-09-11t15-53-00-930056-00-00`

- provider `the_odds_api`
- resource `odds`
- status `completed_with_quarantine`
- records_read 7
- records_accepted 1011
- records_quarantined 46
- data_mode `live`

Raw payloads :

- `raw_the-odds-api-odds-f1cda2454cc6`
- `raw_the-odds-api-odds-8e3a5d5ff092`
- `raw_the-odds-api-odds-ef1bc8d792a0`
- `raw_the-odds-api-odds-1aeb56202731`
- `raw_the-odds-api-odds-d5d20ff9e2f5`
- `raw_the-odds-api-odds-10efb9683d9b`
- `raw_the-odds-api-odds-958de6f8a6ed`

Idempotence : sink SQL `ON CONFLICT DO NOTHING` / ids canoniques stables.
Les tests rejouent les mêmes enveloppes sans dupliquer les ids.

---

## 9. Provenance

Chaque snapshot persisté porte :

- provider `the_odds_api`
- `provider_id` = `{event}:{bookmaker}:1X2:{last_update}`
- `source` = `the-odds-api-v4`
- `data_mode` = `live`
- `raw_payload_id`
- `available_at` / `collected_at` = `bookmakers[].last_update`
- `event_at` = `commence_time`
- marché `1X2`, sélections HOME / DRAW / AWAY

L'enveloppe raw conserve `collected_at` horloge PREDICTA (moment du fetch).
Le domaine Value exige `available_at >= collected_at` **canonique** ; d'où
`last_update` sur les deux champs snapshot, inchangé depuis le pilote odds.

---

## 10. PIT

**PASS**

Deux couches, déjà documentées, **non modifiées** :

1. **Cotes Value / OddsService** : `available_at <= kickoff`. `event_at`
   identifie le match ; il n'exclut pas les cotes pre-match du match cible.
2. **Features ML / PointInTimeStore ingestion** : `event_at < cutoff` et
   `available_at < cutoff`. Un cutoff post-kickoff lève `DataLeakageError` /
   `TemporalLeakageError`.

Exemple runner (Marseille, T = 18:45) : snapshot sélectionné
`available_at=2026-08-21T18:40:17Z`. `before_eligible=true`,
`after_excluded=true`, `leaked=false`.

Politique bookmaker (Value 0.1, inchangée) :

> Last complete 1X2 snapshot with `available_at <= cutoff`, ordered by
> `(available_at, collected_at, snapshot.id)`. Bookmaker identity is not a
> selection criterion; Pinnacle is not preferred because it looks better.

Sur les 17 cibles, l'âge PIT va de **0,07 h** (Angers) à **5,08 h**
(Brentford). Aucun snapshot post-kickoff n'a été retenu.

---

## 11. Anti-leakage

**PASS**

| Contrôle | Résultat |
| --- | --- |
| Snapshot `available_at` ≤ kickoff | oui |
| Snapshot après kickoff refusé | tests ingestion + API |
| Snapshot disponible après cutoff refusé | PIT ingestion `<` ; Value `<=` kickoff |
| Cutoff features > kickoff | `DataLeakageError` / `TemporalLeakageError` |
| HOME/AWAY non retournés | Paris FC unmatched ; pas de flip |
| Cotes hors fenêtre skippées | 20 match ids Sportmonks hors cible |
| Résultat réel | lu seulement au settlement |

Pas de leakage. Les labels parquet `target` / scores ne sont pas des
features Elo.

---

## 12. Prediction

`football-elo-v1-candidate` exclusivement. K, home advantage, dataset,
schema, calibration, registry et code modèle **inchangés**.
`model_status=candidate`. Non promu.

17 prédictions sur les 17 cibles. Features parquet `home_elo_pre` /
`away_elo_pre` / `elo_diff` au cutoff kickoff.

Argmax modèle : 13 HOME, 0 DRAW, 4 AWAY. Hit rate **9/17 = 52,94 %**.
Identique au scoring modèle-only du pilote précédent. Ce n'est **pas** un
ROI.

---

## 13. Odds

Uniquement `the-odds-api-v4`, marché `1X2`, région `eu`.

26 books observés. 20 books complets à 42 snapshots. Incomplets :
everygame 41, codere_it 40, betanysports / matchbook / mybookieag 24,
suprabets 18.

Books retenus au cutoff (last-complete, pas le « meilleur » EV) : betsson,
coolbet, nordicbet, pinnacle, williamhill, winamax_de, winamax_fr.

Âge max sur les 17 cibles : **5,08 h**. Seuil AI Picks `maximum_odds_age=24h`
**non modifié**. `stale_odds` n'a vidé personne. Si un match avait été
exclu pour stale, ce serait un constat, pas un motif de changer le seuil.

---

## 14. Value Engine

**PASS** — parité live.

Formules **exclusives**, version `value-engine-0.1` :

```
implied_probability = 1 / odds
overround = Σ implied_probability
no_vig_probability = implied_probability / overround
edge = model_probability - implied_probability
EV = model_probability × odds - 1
```

`sum(implied) - 1` n'est pas l'overround métier. Tests :
`value_parity_errors` vide. Aucune seconde Value Engine.

---

## 15. AI Picks

Moteur `AiPicksEngine` existant. Pas de second ranking.

- Score : `opportunity_score = EV + Edge`
- Tri : score, EV, edge, fraîcheur, `match_id`, sélection
- Seuils V0.1 : `min_edge=0`, `min_ev=0`, `min_p=0`, `max_odds_age=24h`
- `optimized_on_test=false`

21 opportunités éligibles (plusieurs sélections possibles par match).
Paris FC et Rennes/PSG **absents** du ranking.

---

## 16. Exclusions

Jamais silencieuses.

| Couche | Kind / reason | n | Détail |
| --- | --- | ---: | --- |
| Identité scoring | `isolated_team` | 1 | Troyes vs Paris (`19715629`) |
| Identité scoring | `inverted_home_away` | 1 | Rennes vs PSG (`19715631`), univers labellisé |
| Ingestion | `unmatched_odds_event` | 46 | books Troyes–Paris FC |
| Ingestion sink | skip hors cible | 20 | match ids PL hors fenêtre |
| AI Picks | `negative_ev` | 30 | 17 × 3 − 21 = 30 |
| AI Picks | `stale_odds` | 0 | — |
| AI Picks | `invalid_odds` | 0 | — |

17 × 3 = 51 sélections. 21 picks + 30 `negative_ev` = 51. Rien n'est
supprimé.

---

## 17. Résultats

Settlement théorique, mise fixe 1 unité, 1X2, pas de commission, pas de
push, cote = last-complete au kickoff.

Hits AI Picks (3/21) :

| Match | Sélection | Cote | Issue réelle |
| --- | --- | ---: | --- |
| Hull City vs Manchester United | HOME | 9.20 | HOME |
| Brentford vs Tottenham Hotspur | HOME | 2.12 | HOME |
| Toulouse vs Olympique Lyonnais | AWAY | 2.90 | AWAY |

Les 18 autres lignes AI Picks sont misses. Ce n'est pas une preuve de
qualité de stratégie.

---

## 18. Model performance

Séparé de Value et d'AI Picks. Argmax Elo, **pas** un ROI.

| Métrique | Valeur |
| --- | --- |
| n | 17 |
| Hits | 9 |
| Hit rate | 52,94 % |
| HOME / DRAW / AWAY argmax | 13 / 0 / 4 |
| Sample warning | échantillon insuffisant pour conclure |

Note moteur : « Model argmax accuracy on identity-matched matches. Not a
betting ROI. »

---

## 19. Value performance

Elo argmax **settled** sur la cote PIT (une ligne par match, sans filtre
EV/edge). Ce n'est pas le ranking AI Picks.

| Métrique | Valeur |
| --- | --- |
| n | 17 |
| Hits | 9 |
| Hit rate | 52,94 % |
| Cote moyenne | 2.15 |
| Edge moyen | −0.055 |
| EV moyen | −0.048 |
| Profit théorique | −0.93 u |
| ROI théorique | **−5,47 %** |
| Drawdown max | 3.21 u / 18,9 % du stake cumulé |
| HOME / AWAY | 13 / 4 |

Ligue 1 (n = 7) : ROI −0,86 %. Premier League (n = 10) : ROI −8,7 %.

Baseline naive HOME sur le **même** set de 17 matchs avec cotes : hit rate
52,94 %, ROI théorique **+42,9 %** (tiré par Hull à 9.20). Descriptive
uniquement. Cela ne justifie **pas** de remplacer AI Picks par always-HOME.

**Résultat descriptif, insuffisant pour conclure à une rentabilité future.**

---

## 20. AI Picks performance

Produit `ai-picks-0.1`, une ligne par sélection éligible.

| Métrique | Valeur |
| --- | --- |
| n | 21 |
| Hits | 3 |
| Hit rate | 14,29 % |
| HOME / DRAW / AWAY | 8 / 5 / 8 |
| Cote moyenne | 4.90 |
| Edge moyen | +0.068 |
| EV moyen | +0.396 |
| Profit théorique | −6.78 u |
| ROI théorique | **−32,29 %** |
| Drawdown max | 9.98 u / 39,0 % du stake cumulé |

| Sous-ensemble | n | Hits | ROI théorique |
| --- | ---: | ---: | ---: |
| Ligue 1 | 9 | 1 | −67,8 % |
| Premier League | 12 | 2 | −5,7 % |
| HOME | 8 | 2 | +41,5 % |
| DRAW | 5 | 0 | −100 % |
| AWAY | 8 | 1 | −63,8 % |

EV moyen positif et ROI réalisé négatif coexistent : les longs cotes
éligibles (Arsenal AWAY 16.0, Hull HOME 9.2, etc.) pèsent sur le ranking
sans que n = 21 autorise une conclusion.

**Résultat descriptif, insuffisant pour conclure à une rentabilité future.**

Aucun langage de garantie de gains. Aucune optimisation de seuil a
posteriori.

---

## 21. Reproductibilité

**PASS**

Deux évaluations scoring, mêmes snapshots SQL, même artefact candidate,
même horloge `2026-08-25T00:00:00Z` : fingerprint prédictions / books /
picks / ROI identique.

Ingestion : mêmes enveloppes → mêmes ids canoniques (tests). Live : 7
requêtes, 7 checksums raw. Le JSON QA `workers/ingestion/var/` est
gitignoré ; il n'est pas une source de vérité Git.

CI : live-off, fixtures `soccer_*_persist_near_kickoff.json`, transport
scripté, clé de test seulement.

---

## 22. Limitations

1. n = 17 matchs / 21 picks : pas de preuve de rentabilité, pas d'OOS.
2. Une seule fenêtre d'un weekend. Pas de split train / test.
3. Rennes/PSG : orientation provider **proche du kickoff** = Sportmonks ;
   scoring conserve l'exclusion labellisée du 16 août. Les 67 snapshots
   restent en base append-only.
4. Last-complete peut retenir un book autre que Pinnacle.
5. 1X2 uniquement. Pas d'autres marchés.
6. Elo always-HOME dominant (13/17). Le modèle n'est pas recalibré.
7. Naive HOME a un ROI descriptif supérieur sur **cet** échantillon ; ce
   n'est pas une promotion de stratégie.
8. PIT ingestion (`<` cutoff) et Value (`<=` kickoff) restent deux
   contrats. Documentés, non unifiés dans ce run.
9. 20 events hors fenêtre observés puis skippés : le provider historical
   n'est pas borné aux 17 matchs, le **sink** l'est.

---

## 23. Verdict

| Gate | Résultat |
| --- | --- |
| 17 cibles traitées | **PASS** |
| 2 rejets scoring conservés | **PASS** |
| Aucun match canonique inventé | **PASS** |
| Odds réelles persistées | **PASS** (1011) |
| Raw + provenance | **PASS** |
| PIT | **PASS** |
| Anti-leakage | **PASS** |
| Value parity | **PASS** |
| AI Picks parity | **PASS** |
| Reproductibilité | **PASS** |
| Modèle / seuils inchangés | **PASS** |
| Pas de backfill massif | **PASS** (7 requêtes) |
| Pas de donnée synthétique dans le scoring réel | **PASS** |
| Clé API absente du git | **PASS** |
| `stale_odds` artificiel | **évité** (âge < 24 h) |

**GO WITH CONDITIONS**

GO ne signifie pas « AI Picks rentable ». Le ROI théorique est négatif.
Même s'il avait été positif, le constat resterait :

**Résultat descriptif, insuffisant pour conclure à une rentabilité future.**

Conditions :

1. `football-elo-v1-candidate` reste candidate.
2. Value Engine 0.1 et AI Picks 0.1 restent inchangés (pas de tuning).
3. Ne pas présenter n = 17 ou n = 21 comme une preuve de ROI.
4. Ne pas élargir à une grille 5 minutes sans décision budget crédits.
5. CI live-off.
6. Conservé : Paris FC unmatched ; Rennes/PSG hors univers scoring 17.

Quality gates locales (`.venv` de chaque package ; `python` n'est pas
sur le PATH système). CI live-off. OpenAPI inchangé. Aucun secret.
Aucune promotion.

| Commande | Résultat |
| --- | --- |
| `verify:ingestion` | ruff + mypy + **159 passed** |
| `verify:api` | ruff + mypy + **585 passed** |
| `verify:ml` | ruff + mypy + **29 passed** |
| `verify:web` / `verify:openapi` | openapi + typecheck + lint + **283 passed** + build |
| `verify:all` | **PASS** (les quatre gates ci-dessus via `.venv`) |

**NO-GO évité** : persistance réelle, PIT, anti-leakage, parité, pas de
flip HOME/AWAY, pas de secret, pas de promotion.

---

## 24. Prochaines étapes

1. Laisser le candidat **non promu**.
2. Ne pas tuner `minimum_edge` / `maximum_odds_age` sur ce weekend.
3. Si un run plus large est décidé : même cadence bornée (1 snapshot /
   ligue / jour), cap crédits explicite, arrêt propre, pas de 5 minutes.
4. Traiter Rennes/PSG comme dossier d'identité **temporel** (orientation
   provider au 16 août vs au kickoff) dans un run dédié, sans mélanger
   avec un tuning de stratégie.
5. Séparer durablement MODEL / VALUE / AI PICKS dans tout rapport futur.

---

## Commandes

```bash
# Persist borné (live, crédits réels, pas --dry-run)
cd workers/ingestion
python -m predicta_ingestion persist-historical-odds-pilot

# Scoring 0 crédit
cd apps/api
python -m app.backtesting persisted-weekend
```

Tests déterministes : `tests/test_persist_historical_odds_pilot.py`,
`apps/api/tests/test_persist_historical_odds_weekend.py`. Aucun test unitaire
n'appelle The Odds API.
