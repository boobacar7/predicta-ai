# Runtime pre-match — validation

**Branche :** `agent/data/prematch-runtime`  
**Modèle :** `football-elo-v1-candidate` — **non promu**  
**Value Engine :** `value-engine-0.1` — **non modifié**  
**AI Picks ranking :** `ai-picks-0.1` — **non modifié**  
**Analyst renderer :** inchangé, LLM réel **OFF** (`deterministic-v0.1`)  
**Provider cotes :** `the-odds-api-v4` / `data_mode=live`  
**Verdict :** **GO WITH CONDITIONS**

Le runtime permet désormais à un match **scheduled** disposant d'une identité
canonique, de features PIT unlabeled, d'une prédiction candidate et d'un
snapshot Odds API 1X2 live de traverser Prediction → Value → AI Picks →
AI Analyst. Aucun mock n'intervient sur ce chemin. Le dataset labellisé
`football-1x2-history-0.3` n'a pas été réentraîné.

---

## 1. Migration 0004

**PASS**

`0004_odds_history` est le head Alembic. Elle n'a pas été réécrite : la
logique métier (backfill `data_mode='mock'`, `available_at >= collected_at`,
`data_mode IN ('mock','live')`, déduplication `odds_selections`, unique
`(provider, provider_id)`, colonnes NOT NULL) est déjà correcte.

Sécurisation runtime (hors CI) :

- `require_odds_history_schema()` refuse `ingest-odds` si
  `alembic_version ≠ 0004_odds_history` ou si `provider_id` /
  `available_at` / `collected_at` / `data_mode` / `source` manquent.
- Persist SQL reste append-only (`ON CONFLICT DO NOTHING`).
- Tests source (API + ingestion) couvrent le contrat. **Aucun Postgres
  n'est ajouté à la CI.**

Environnement local QA : `alembic_version = 0004_odds_history`.

## 2. Alias

**PASS**

Table versionnée `the-odds-api-team-aliases-v1`.

Schéma : `provider`, `provider_team_name`, `canonical_team_id`,
`canonical_team_name`, `evidence`.

Propriétés :

- exact, déterministe, one-to-one `(provider, slug(provider_team_name))` ;
- un alias → un seul `canonical_team_id` ;
- table ambiguë refusée à la validation ;
- pas de fuzzy, pas de Levenshtein, pas de LLM.

Alias démontrés (validation Odds API 2026-09-11) :

| Odds API | Canonical | Id |
| --- | --- | --- |
| Bournemouth | AFC Bournemouth | `tm_football-sportmonks-52` |
| Brighton and Hove Albion | Brighton & Hove Albion | `tm_football-sportmonks-78` |
| Marseille | Olympique Marseille | `tm_football-sportmonks-44` |
| AS Monaco | Monaco | `tm_football-sportmonks-6789` |
| Angers | Angers SCO | `tm_football-sportmonks-776` |
| Lille | LOSC Lille | `tm_football-sportmonks-690` |
| Le Mans FC | Le Mans | `tm_football-sportmonks-7758` |
| RC Lens | Lens | `tm_football-sportmonks-271` |
| Lyon | Olympique Lyonnais | `tm_football-sportmonks-79` |

Matching : clé exacte `football\|home\|away\|kickoff`, puis réécriture
explicite des slugs aliasés. Les événements non matchés restent en
quarantaine `unmatched_odds_event`.

### Isolation Paris

Aucun alias n'existe pour `Paris`, `Paris FC`, `Paris Saint-Germain`,
`Paris Saint Germain`, `PSG`.

Slugs distincts : `paris` / `paris-fc` / `paris-saint-germain` / `psg`.
`Paris Saint-Germain` et `Paris Saint Germain` partagent le même slug
(exact, pas un alias). Sportmonks persiste `Paris`
(`tm_football-sportmonks-4508`) et `Paris Saint Germain`
(`tm_football-sportmonks-591`). **Paris FC n'est pas fusionné avec Paris.**

## 3. PIT pre-match

**PASS**

Cause du gap : `build_ml_dataset` n'étiquette que les matchs **finished**.
Les scheduled étaient rejetés (`not_finished`, 1890 lignes dans le snapshot
0.3). `ParquetPitFeatureStore` ne lisait que ce parquet labellisé →
`PitFeaturesUnavailableError` pour tout `match_id` upcoming.

Correctif : overlay unlabeled `build-prematch-features`.

- Features au cutoff `T = kickoff` exclusivement.
- Faits utilisés : `available_at < T` et `event_at < T`.
- Le match cible n'entre pas dans ses rolling windows / H2H / Elo update.
- Aucun score scheduled n'est inventé ni utilisé.
- Elo : mêmes paramètres que le candidat (`K=20`, HA `+80`, initial 1500).
- `reconstruct_pre_match_elo` (dataset labellisé) est inchangé.
- `snapshot_pre_match_elo` snapshotte aussi les unlabeled sans les mettre
  à jour.
- Checks anti-leakage API inchangés : cutoff `< kickoff` → 422 PIT ;
  cutoff `> kickoff` → 409 leakage.

Snapshot local QA (SQL Sportmonks, sans re-fetch) :

- 1890 fixtures scheduled
- 0 rejet overlay
- `dataset_version = football-1x2-history-0.3` (schéma candidat)
- `feature_origin = prematch_unlabeled`
- artefact gitignoré : `workers/ingestion/var/football-1x2-prematch.parquet`

Insuffisance structurelle documentée, non contournée : le parquet
**labellisé** ne peut pas servir l'inférence upcoming. L'overlay est un
artefact d'inférence, pas un nouveau dataset d'entraînement. Un club sans
historique finished conserve Elo 1500.

## 4. Modèle

**PASS** (inchangé)

`football-elo-v1-candidate` reste `candidate`. Pas de réentraînement, pas
de recalibrage, pas de changement K / HA / dataset / registry, pas de
promotion. Les probabilités du match réel ci-dessous viennent de
l'artefact candidat chargé tel quel.

## 5. Match réel utilisé

Liverpool vs Fulham, Premier League.

| Champ | Valeur |
| --- | --- |
| `match_id` | `mth_football-sportmonks-19722167` |
| Statut | `scheduled` |
| Kickoff | `2026-09-12T14:00:00Z` |
| Home / away | Liverpool / Fulham |
| Canonical teams | `tm_football-sportmonks-8` / `tm_football-sportmonks-11` |
| Identité | SQL Sportmonks |
| PIT overlay | `home_elo_pre=1603.8535`, `away_elo_pre=1486.9284`, `elo_diff=116.9251` |
| `data_mode` features | `live` |

## 6. Odds réelles

**PASS**

25 snapshots live 1X2, `source=the-odds-api-v4`, `data_mode=live`.
Pinnacle (référence QA précédente) : `1.45 / 5.02 / 6.69` à
`2026-09-11T13:19:43Z`.

Value Engine v0.1 sélectionne le dernier snapshot complet
`available_at <= cutoff` dans l'ordre du repository. Ici : `pmu_fr`
`1.41 / 4.90 / 6.40` à `2026-09-11T13:19:44Z` (même seconde que
Betfair / GTbets, 1 s après Pinnacle). Contrat existant, non modifié.

## 7. Prediction

**PASS**

`football-elo-v1-candidate` @ cutoff kickoff :

| Issue | Probabilité |
| --- | ---: |
| HOME | 0.5513967003830924 |
| DRAW | 0.23940763749495694 |
| AWAY | 0.20919566212195062 |
| Somme | 1.0 |

`model_status=candidate`. Aucune cote n'entre dans le modèle.

## 8. Value

**PASS**

`value-engine-0.1` sur cotes `pmu_fr` live. Formules inchangées :

`implied = 1 / odds`, `overround = Σ implied`, `no_vig = implied / overround`,
`edge = p_model - implied`, `EV = p_model × odds - 1`.

| | HOME | DRAW | AWAY |
| --- | ---: | ---: | ---: |
| Odds | 1.41 | 4.90 | 6.40 |
| Implied | 0.709220 | 0.204082 | 0.156250 |
| Edge | −0.157823 | +0.035326 | +0.052946 |
| EV | −0.222531 | +0.173097 | +0.338852 |

Overround ≈ 1.06955. `odds_source=the-odds-api-v4`, `data_mode=live`.

## 9. AI Picks

**PASS** (pipeline) — **CONDITION** (univers / stale)

Le ranking n'a pas été modifié. L'univers V0.1 reste
`[mth_football-sportmonks-19719892]` (Lincoln).

Quand le match Liverpool–Fulham est injecté comme candidat, le moteur
consomme la prédiction candidate + les cotes live **sans recalcul
frontend**. Aux seuils V0.1 existants, HOME / DRAW / AWAY sont exclus
`stale_odds` : `available_at` 2026-09-11T13:19:44Z vs cutoff kickoff
2026-09-12T14:00:00Z ≈ 24 h 40 min, seuil `maximum_odds_age=24h`.

C'est le contrat de ranking actuel, pas un fallback mock. Un tick odds
plus proche du coup d'envoi (ou un cutoff de liste plus proche de
`available_at`) ferait passer DRAW/AWAY en éligible (EV positifs).

## 10. AI Analyst

**PASS**

Narrator `deterministic-v0.1`. LLM réel OFF. Le contexte assemblé est
réel : identité Liverpool–Fulham, probabilités candidate, value live
`the-odds-api-v4`, `data_mode=live`. Favorite modèle : HOME (55,1 %).
Renderer sécurisé inchangé.

## 11. Mock / live isolation

**PASS**

- CI live-off, fixtures only.
- `LiveOddsProvider` ne retombe jamais sur mock.
- `MockOddsProvider` ne sert pas Liverpool–Fulham.
- Overlay prematch `data_mode=live` ; history parquet inchangé.
- Aucune clé API dans Git.
- `ingest-odds` refuse le runtime si 0004 manque.

## 12. Quality gates

**PASS**

| Gate | Résultat |
| --- | --- |
| `verify:ingestion` | ruff + mypy + **139** pytest |
| `verify:ml` | ruff + mypy + **27** pytest |
| `verify:api` | ruff + mypy + **556** pytest |
| `verify:web` | OpenAPI inchangé + typecheck + lint + **283** pytest + build |

CI live-off inchangée. Aucun Postgres dans la CI. Aucun appel réseau.
Les scripts `npm run verify:*` appellent `python` ; exécution locale via
le `.venv` de chaque package (`python` n'est pas sur le PATH système).

## 13. Limites

1. Overlay prematch gitignoré : il faut
   `python -m predicta_ingestion build-prematch-features` sur un SQL
   déjà ingéré. Pas de backfill historique massif.
2. Paris FC (Odds API) ≠ Paris (Sportmonks) reste non matché, volontairement.
3. Univers AI Picks V0.1 inchangé (Lincoln).
4. Seuil stale 24 h vs un unique tick current-odds.
5. Value Engine choisit le dernier book complet, pas Pinnacle par politique.
6. Clubs sans historique finished : Elo 1500, forme 0. C'est du PIT honnête,
   pas une invention.
7. Le candidat ne sert que le snapshot pre-kickoff (cutoff exact).

## 14. HIGH / MEDIUM / LOW

### HIGH (0)

Aucun blocker runtime restant sur 0004, l'alias explicite, le PIT scheduled
ou la consommation candidate + cotes live.

### MEDIUM (2)

- **M-01** — Paris FC / Paris restent distincts ;  le matching live
  8/19 d'origine n'est pas entièrement refermé (volontaire).
- **M-02** — AI Picks V0.1 : univers Lincoln inchangé ; sur Liverpool–Fulham
  le tick current-odds est `stale_odds` au cutoff kickoff (+24 h).

### LOW (3)

- **L-01** — Tie-break repository entre books iso-`available_at` (pmu_fr vs
  Pinnacle −1 s).
- **L-02** — Overlay 1890 lignes local, non versionné dans Git (comme le
  parquet 0.3).
- **L-03** — `PersistResult.inserted` compte toujours les tentatives.

## 15. Verdict

**GO WITH CONDITIONS**

La chaîne pre-match réelle fonctionne pour un scheduled canonique + PIT
unlabeled + candidat Elo + cotes `the-odds-api-v4` live, sans mock
silencieux et sans promotion du modèle.

Conditions :

1. `football-elo-v1-candidate` reste candidate.
2. L'univers / ranking AI Picks V0.1 n'est pas élargi.
3. Ne pas aliaser Paris / Paris FC / PSG.
4. Appliquer Alembic 0004 partout avant `ingest-odds`.
5. Reconstruire l'overlay prematch après ingestion Sportmonks, sans
   mélanger ces lignes au dataset d'entraînement.
