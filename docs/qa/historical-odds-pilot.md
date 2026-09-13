# Historical odds — pilote borné

**Branche :** `agent/qa/historical-odds-pilot`  
**Modèle :** `football-elo-v1-candidate` — **non promu**  
**Value Engine :** `value-engine-0.1` — **non modifié**  
**AI Picks ranking :** `ai-picks-0.1` — **non modifié**  
**Analyst renderer :** inchangé, LLM réel **OFF** (`deterministic-v0.1`)  
**Provider cotes :** The Odds API v4, endpoint **historical**, région `eu`, marché `h2h` → `1X2`  
**Verdict :** **GO WITH CONDITIONS**

Ce pilote valide l'architecture historique (fetch → raw immuable → canonical
odds → PIT → prediction candidate → Value → AI Picks → Analyst) et **mesure
le coût réel** avant toute montée en charge. Ce n'est **pas** un backfill.
Ce n'est **pas** une preuve de rentabilité.

La clé `THE_ODDS_API_KEY` est lue depuis l'environnement local. Elle n'apparaît
dans aucun log, fixture, rapport JSON ou fichier Git.

---

## 1. Périmètre

Strictement :

| Contrôle | Valeur |
| --- | --- |
| Ligues | Premier League (`soccer_epl`), Ligue 1 (`soccer_france_ligue_one`) |
| Marché | `h2h` / canonique `1X2` |
| Région | `eu` |
| Requêtes max | **4** (`MAX_PILOT_REQUESTS`) |
| CLI | `python -m predicta_ingestion historical-odds-pilot --dry-run` |
| CI | live-off, fixtures only, inchangée |

Toute autre ligue ou un `max_requests > 4` est rejeté (`ValidationError`).

Run live QA : `--dry-run` (pas d'écriture PostgreSQL ni raw store). L'append-only
raw / canonical est couvert par les tests d'ingestion.

---

## 2. Dates

Fenêtre unique, volontairement courte :

| Horodatage | Rôle |
| --- | --- |
| `2026-08-16T11:00:00Z` | `as_of_before` — snapshot demandé **avant** T |
| `2026-08-16T14:00:00Z` | cutoff PIT **T** |
| `2026-08-16T15:00:00Z` | `as_of_after` — snapshot demandé **après** T |

Le provider ne interpolle pas. Il renvoie le snapshot **le plus proche ≤ `date`** :

| Demandé | `snapshot_timestamp` | `previous_timestamp` | `next_timestamp` |
| --- | --- | --- | --- |
| 11:00:00Z | **10:55:38Z** | 10:50:38Z | 11:00:38Z |
| 15:00:00Z | **14:55:38Z** | 14:50:38Z | 15:00:39Z |

Grille observée : **5 minutes**. Un `snapshot_timestamp` strictement postérieur
à la date demandée serait un échec (`historical_interpolation`).

Les événements couverts kickent du **21 au 24 août 2026** (prochaine journée
visible au 16 août).

---

## 3. Compétitions

Uniquement Premier League et Ligue 1. Les cinq autres ligues V1
(La Liga, Bundesliga, Serie A, Champions League, MLS) **n'ont pas été
appelées**.

---

## 4. Events

**19** événements uniques The Odds API (10 EPL + 9 Ligue 1), identiques sur
les deux timestamps.

EPL (10) : Arsenal–Coventry City, Hull City–Manchester United, Nottingham
Forest–Leeds United, Ipswich Town–Sunderland, Everton–Crystal Palace,
Brentford–Tottenham Hotspur, Brighton & Hove Albion–Aston Villa, Manchester
City–AFC Bournemouth, Newcastle United–Liverpool, **Fulham–Chelsea**
(kickoff `2026-08-24T19:00:00Z`).

Ligue 1 (9) : Marseille–Strasbourg, Lens–Auxerre, Toulouse–Lyon, Nice–Lorient,
Le Mans–Brest, Angers–Lille, Le Havre–Monaco, plus les deux rejets ci-dessous.

---

## 5. Matchs matchés

**17** / 19. `exact_matches=17`, `alias_matches=0`, `false_match_count=0`.

Matching : clé naturelle exacte `football|home|away|kickoff`, puis réécriture
explicite des slugs aliasés (`the-odds-api-team-aliases-v1`). Pas de fuzzy,
pas de similarité, pas de LLM. Aucun match Sportmonks n'est créé depuis Odds API.

Sur cette fenêtre, les noms provider slugifient déjà vers Sportmonks
(ex. `Brighton & Hove Albion`, `AFC Bournemouth`, `Olympique Marseille`).
Les aliases explicites restent nécessaires sur d'autres journées (validation
live 2026-09-11) ; ils sont exercés par les fixtures du pilote, pas par ce
weekend-ci.

PIT subject : `mth_football-sportmonks-19722203` (Arsenal vs Coventry City,
kickoff `2026-08-21T19:00:00Z`, résultat réel 3–0, statut `finished`).

---

## 6. Rejets

**2** événements, quarantaine `unmatched_odds_event`. Précision > recall.

| Odds API (clé naturelle) | Sportmonks observé | Cause |
| --- | --- | --- |
| `football\|troyes\|paris-fc\|2026-08-22T18:45:00+00:00` | Troyes vs **Paris** (`tm_football-sportmonks-4508`) | Isolation Paris / Paris FC / PSG. Aucun alias. |
| `football\|paris-saint-germain\|rennes\|2026-08-23T18:45:00+00:00` | **Rennes vs Paris Saint Germain** | Home/away **inversés**. Un match sur la paire dans le mauvais sens serait un faux match 1X2. Rejet correct. |

43 quarantaines book-level × 2 timestamps Ligue 1 = les books des 2 events
rejetés. Aucun snapshot n'est inséré pour ces events.

---

## 7. Snapshots

**756** snapshots canoniques 1X2 acceptés (dry-run, mémoire).

```
226 + 226 (EPL × 2) + 152 + 152 (Ligue 1 matchée × 2) = 756
```

Chaque snapshot porte : provider event id, `commence_time` → `event_at`,
home/away, bookmaker, market `1X2`, outcomes `HOME`/`DRAW`/`AWAY`,
`last_update` → `available_at` = `collected_at` canonique, `raw_payload_id`.

Tests : 4 enveloppes raw append-only, `data_mode=live`, endpoint
`historical_odds`, checksum, clé API absente du store.

Idempotence : un second ingest des mêmes enveloppes ne duplique pas les ids
canoniques (`ON CONFLICT DO NOTHING` / sink mémoire).

---

## 8. Bookmakers

**24** books région `eu` observés. Aucun book n'a été choisi parce qu'il
« performe mieux ».

| Book | Snapshots | Couverture |
| --- | ---: | --- |
| betclic_fr, betfair_ex_eu, betonlineag, betsson, codere_it, coolbet, leovegas_se, marathonbet, nordicbet, onexbet, pinnacle, pmu_fr, sport888, tipico_de, unibet_fr, unibet_nl, unibet_se, williamhill, winamax_de, winamax_fr | 34 chacun | 17 matchs × 2 timestamps, complet |
| gtbets | 22 | manquant sur une partie de l'univers |
| matchbook | 20 | manquant |
| mybookieag | 20 | manquant |
| **suprabets** | **14** | le plus incomplet |

Délais : `last_update` des books se situe quelques secondes avant
`snapshot_timestamp` (ex. PIT selected `available_at=2026-08-16T10:55:27Z`
vs snapshot provider `10:55:38Z`). Pas d'invention d'horodatage.

**Règle déterministe (inchangée, Value Engine v0.1) :**

> Last complete 1X2 snapshot with `available_at <= cutoff`, ordered by
> `(available_at, collected_at, snapshot.id)`. Bookmaker identity is not a
> selection criterion; Pinnacle is not preferred because it looks better.

Le book retenu au cutoff T pour Arsenal–Coventry est celui dont
`available_at` est le plus tardif **strictement avant** T, pas celui au
meilleur EV.

---

## 9. PIT

**PASS**

Cutoff T = `2026-08-16T14:00:00Z`. Match `mth_football-sportmonks-19722203`.

| Contrôle | Résultat |
| --- | --- |
| Snapshot avant T éligible | **oui** (`available_at=2026-08-16T10:55:27Z`) |
| Snapshot après T exclu | **oui** (14:55:38Z / last_update ≥ 14:00) |
| Fuite | `leaked=false` |
| `pit.passed` | **true** |

Deux couches, volontairement distinctes :

1. **Odds** : `available_at < T` (ingestion PIT) / `available_at <= cutoff`
   (API Value). `event_at` (kickoff) identifie le match ; il **n'exclut pas**
   les cotes pre-match du match cible.
2. **Features ML** : `available_at < T` **et** `event_at < T`. Le match cible
   n'entre pas dans Elo / forme / H2H. Un cutoff `> kickoff` lève
   `DataLeakageError`.

Le cutoff T du 16 août est un test de **snapshot**. La prédiction historique
d'Arsenal–Coventry utilise T = kickoff `2026-08-21T19:00:00Z`.

---

## 10. Anti-leakage

**PASS**

- Snapshot demandé après T jamais sélectionné à T.
- `features_for_match` refuse un cutoff post-coup d'envoi.
- Le match cible est absent de `prior_matches`.
- Elo / forme d'Arsenal–Coventry : `home_elo_pre=1740.9886`,
  `away_elo_pre=1500.0` (Coventry sans historique finished — cold start
  honnête, pas une invention), `cutoff_policy=pre_kickoff`.
- Dataset labellisé `football-1x2-history-0.3` **non réentraîné**.
- Pas de classement post-match, pas de stats post-cutoff, pas de résultat
  du match cible dans les features.

---

## 11. Predictions

**PASS** (moteur inchangé)

`football-elo-v1-candidate` reste `candidate`. K, home advantage, calibration,
dataset, architecture et registry **non modifiés**.

Prédiction historique Arsenal–Coventry au cutoff kickoff, features parquet
0.3 uniquement :

| Issue | Probabilité |
| --- | ---: |
| HOME | 0.6315971886873162 |
| DRAW | 0.21435861511539392 |
| AWAY | 0.15404419619728993 |
| Somme | 1.0 |

`model_status=candidate`, `dataset_version=football-1x2-history-0.3`,
`feature_schema_version=football-1x2-features-0.3`, `data_mode=live`.
Outcome réel : HOME (3–0). **Un match n'est pas un backtest de rentabilité.**

Les 17 matchs matchés sont présents dans le parquet labellisé. Ce pilote
n'a **pas** scoré les 17 avec les cotes historical persistées (dry-run).

---

## 12. Value

**PASS**

Formules **identiques** au live, version `value-engine-0.1` :

```
implied = 1 / odds
overround = Σ implied
no_vig = implied / overround
edge = p_model - implied
EV = p_model × odds - 1
```

Tests API : parité historique/live, exclusion du snapshot après T, sélection
du dernier book complet **même s'il a un EV moins bon** que Pinnacle,
reproductibilité bit-à-bit du `model_dump()`.

Backtest descriptif (fixture, **pas** une preuve de ROI) : marché 2.00 / 4.00
/ 5.00, p_model 0.60 / 0.20 / 0.20, sélections `ev>0` et `edge>0`, hit rate
et EV théorique calculés de façon déterministe.

---

## 13. AI Picks

**PASS** (pipeline) — ranking **inchangé**

Source de `_rank_opportunities` : `-opportunity_score` puis `-ev`.
Version `ai-picks-0.1`. Un snapshot historical 1X2 traverse Value → Picks
sans recalcul frontend et sans élargir l'univers V0.1.

---

## 14. Analyst

**PASS**

Narrator `deterministic-v0.1`. LLM réel OFF. Le renderer n'a pas été
modifié. Le contexte assemblé porte le candidat + cotes `the-odds-api-v4`
`data_mode=live`.

---

## 15. Crédits consommés

**Mesure réelle** (headers `x-requests-last` / `x-requests-used` /
`x-requests-remaining`). Aucune hypothèse.

| Exécution | Requêtes | Crédits | `requests_used` fin | `requests_remaining` fin |
| --- | ---: | ---: | ---: | ---: |
| Run 1 (même fenêtre, plus tôt dans cette validation) | 4 | **40** | 40 | 19960 |
| Run 2 (rapport capturé, reconstruction) | 4 | **40** | 80 | 19920 |
| **Total session QA** | **8** | **80** | 80 | 19920 |

Chaque requête historical : **`x-requests-last=10`**. Conforme à la doc
provider (10 × 1 région × 1 marché).

Le run 2 est une **reconstruction** du même dataset + mêmes timestamps :
identity 19 / 17 / 2 / 756 identique au run 1. Reproductibilité live **PASS**.

Coût d'**une** exécution du pilote borné : **40 crédits**.

---

## 16. Coûts

### Mesuré (ce pilote)

| Unité | Crédits |
| --- | ---: |
| 1 requête historical (EPL ou Ligue 1, `eu`, `h2h`) | **10** |
| 1 timestamp × 1 ligue (tous les events de la ligue) | **10** |
| Fenêtre 2 ligues × 2 timestamps | **40** |
| Coût incrémental d'un event supplémentaire **dans le même snapshot ligue** | **0** |

10 events EPL coûtent autant que 9 events Ligue 1 : **10 crédits**. Le fetch
est par ligue-timestamp, pas par match.

USD : **non mesuré**. Le plan local n'est pas un output de l'API. La
documentation provider indique un free tier 500 crédits/mois (historical
payant) et des plans payants. Aucune conversion $/crédit n'est inventée ici.

### Estimation (explicitement non mesurée)

Hypothèses **hors mesure** : nombre de journées ≈ 38 (PL) / ≈ 34 (Ligue 1) ;
les 5 autres ligues V1 ont le **même tarif documenté** 10 crédits/requête
(non rejoué dans ce pilote) ; 1 snapshot par journée et par ligue.

| Scénario | Calcul | Crédits | Statut |
| --- | --- | ---: | --- |
| 1 saison PL, 1 snap/journée | 38 × 10 | 380 | estimation |
| 1 saison Ligue 1, 1 snap/journée | 34 × 10 | 340 | estimation |
| 1 saison PL+L1, 1 snap/journée | 380+340 | 720 | estimation |
| 1 saison PL+L1, 2 snaps/journée (comme ce pilote) | 720 × 2 | 1440 | estimation |
| 3 saisons PL+L1, 1 snap/journée | 720 × 3 | 2160 | estimation |
| 7 compétitions V1, 1 saison, 1 snap/journée | 7 × 38 × 10 | 2660 | estimation (5 ligues non mesurées) |

Une cadence 5 minutes sur une saison entière serait un backfill : **hors
périmètre**, coût non chiffré ici.

À 10 crédits / ligue-timestamp, le pilote 40 crédits est **acceptable**.
Un backfill dense ne l'est pas tant que la cadence n'est pas bornée.

---

## 17. Limitations

1. `--dry-run` : le raw store et PostgreSQL ne reçoivent pas les 756
   snapshots du run live. L'architecture append-only est testée, pas
   encore peuplée en SQL pour ce weekend.
2. 2/19 unmatched (Paris FC isolé, PSG/Rennes inverted). Volontaire.
3. `alias_matches=0` sur **cette** fenêtre ; aliases exercés en fixtures.
4. Pas de scoring Value/Picks des 17 matchs sur cotes historical persistées.
5. Elo cold start (Coventry 1500 / forme 0) : PIT honnête.
6. Value Engine = dernier 1X2 complet, pas un book de référence.
7. Univers AI Picks V0.1 (Lincoln) non élargi.
8. Les 5 autres ligues V1 ne sont pas dans le pilote.

---

## 18. HIGH / MEDIUM / LOW

### HIGH (0)

Aucune fuite temporelle, aucun faux match, aucun calcul Value divergent,
aucun secret dans Git, pas de promotion du candidat.

### MEDIUM (3)

- **M-01** — 2 events rejetés (Paris FC isolé ; home/away PSG/Rennes). La
  précision est correcte ; un backfill plus large devra tracer les
  inversions home/away sans fuzzy.
- **M-02** — Dry-run live : pas de persistance SQL/raw de ce weekend.
  L'inférence historical bout-en-bout en production exige un persist
  borné, pas un backfill.
- **M-03** — Backtest descriptif (fixture + 1 prediction finished). Ne pas
  le présenter comme un ROI.

### LOW (4)

- **L-01** — `snapshot_timestamp` ≤ date demandée (offset ~4 min 22 s).
- **L-02** — Couverture books inégale (suprabets 14 vs 34).
- **L-03** — Tie-break last-complete peut retenir un book autre que Pinnacle.
- **L-04** — Clubs sans historique finished : Elo 1500.

---

## 19. Recommandations

1. **Ne pas** promouvoir `football-elo-v1-candidate`.
2. **Ne pas** lancer de backfill 5 minutes. Cadence = 1 (voire 2) snapshot(s)
   par journée et par ligue, en marchant sur `previous_timestamp` /
   `next_timestamp` provider.
3. Persister le prochain run borné **sans** `--dry-run` une fois 0004
   confirmé, pour ouvrir Prediction → Value sur les 17 matchs.
4. Conserver l'isolation Paris / Paris FC / PSG.
5. Traiter les inversions home/away comme rejets (ou règle explicite
   documentée), jamais comme un match flou.
6. Ne pas figer Pinnacle comme book de référence sans décision produit.
7. Recalculer le coût des 5 autres ligues par **mesure**, pas par analogie
   seule, avant un budget saisonnier.

---

## 20. Verdict

Quality gates (exécution locale via le `.venv` de chaque package ; `python`
n'est pas sur le PATH système). CI live-off inchangée. OpenAPI inchangé.

| Gate | Résultat |
| --- | --- |
| `verify:api` | ruff + mypy + **564** pytest |
| `verify:ingestion` | ruff + mypy + **151** pytest |
| `verify:ml` | ruff + mypy + **27** pytest |
| `verify:web` | OpenAPI inchangé + typecheck + lint + **283** pytest + build |
| `verify:all` | concaténation des quatre gates — **PASS** |

**GO WITH CONDITIONS**

L'endpoint historical The Odds API fonctionne. Les payloads restent
immuables (tests). Le matching exact + aliases explicites refuse les
événements ambigus. Le PIT distingue snapshot avant T / après T. Le
candidat Elo et Value Engine v0.1 ne changent pas. AI Picks / Analyst
consomment le même contrat, LLM OFF. Le coût unitaire est **mesuré** :
10 crédits par ligue-timestamp, 40 pour ce pilote.

Conditions :

1. `football-elo-v1-candidate` reste candidate.
2. Value Engine `value-engine-0.1` et ranking `ai-picks-0.1` inchangés.
3. Pas de backfill dense ; pas d'interpolation de timestamps.
4. Ne pas aliaser Paris / Paris FC / PSG ; ne pas matcher un 1X2 inversé.
5. Ne pas présenter les stats descriptives comme une rentabilité.
6. CI live-off inchangée.

**NO-GO évité** : pas de fuite temporelle, pas de faux match, snapshots
non interpolés, Value identique au live.
