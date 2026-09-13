# Value / AI Picks Pilot Analysis

**Branche :** `agent/ml/analyze-value-ai-picks-pilot`  
**Nature :** analyse uniquement. Aucun modèle, seuil, ranking, bookmaker ou snapshot n'a été modifié.  
**Run analysé :** `docs/qa/historical-odds-value-ai-picks-pilot.md`  
**Artefact scoring (gitignoré, `var/`) :** `workers/ingestion/var/persisted-weekend-score.json`  
**Modèle :** `football-elo-v1-candidate` — non promu  
**Value Engine :** `value-engine-0.1`  
**AI Picks :** `ai-picks-0.1`  
**Verdict :** **NO ANOMALY FOUND**

Cette branche ne déclare ni rentabilité ni non-rentabilité. Avec n = 17 matchs / 21 picks, le constat économique reste : **insuffisant pour conclure**.

---

## 1. Executive Summary

Les chiffres **21 sélections**, **14,29 % de hit rate** (3/21) et **−32,29 % de ROI théorique** (arrondi −32,3 %) sont **mathématiquement cohérents** avec le moteur de scoring. Ils ne sont pas le produit d'un ROI « par match » ni d'un hit rate Elo.

Ce qui s'est passé, mesuré et non supposé :

1. **AI Picks 0.1 n'est pas Elo argmax.** 15 des 21 picks (71 %) sont une issue **différente** du favori modèle. Seulement 6 picks reproduisent l'argmax.
2. La spécification autorise **plusieurs sélections par match** (au plus une ligne par `match/marché/sélection`). 5 matchs ont 2 picks, 11 ont 1 pick, 1 a 0 pick (Everton). Aucun n'a 3 picks.
3. Le filtre V0.1 `EV ≥ 0` et `edge ≥ 0` est, pour des cotes décimales > 1, **équivalent**. Il a retenu les 21 issues à EV positif parmi 51 issues possibles (17 × 3) et exclu 30 `negative_ev`.
4. **11 des 17 argmax Elo ont un EV négatif** (favoris à cote courte, marge bookmaker). AI Picks les saute et prend DRAW / AWAY / outsider HOME. Elo argmax a pourtant 9 hits / 17 (52,94 %) ; AI Picks n'en partage qu'**un** (Brentford HOME).
5. Les 3 hits AI Picks sont Hull HOME à 9,20 (+8,20 u), Toulouse AWAY à 2,90 (+1,90 u) et Brentford HOME à 2,12 (+1,12 u). Les 18 misses = −18 u. Net **−6,78 u / 21 u = −32,29 %**.
6. Formules Value, ranking, PIT, exclusions, parité et reproductibilité **se reconstruisent**. Aucun bug de calcul moteur n'a été trouvé. Un écart de **documentation** existe dans le rapport source : drawdown max rapporté à 39,0 % alors que le JSON et la formule moteur donnent **47,52 %** (9,98 / 21).

Le mauvais résultat AI Picks, sur **cet** échantillon, coïncide avec une sélection de cotes plus longues (moyenne 4,90 vs 2,15 pour l'argmax) et d'issues non-argmax. Cela n'établit pas une cause unique (modèle vs prix vs variance) : n est trop petit. Intervalle de Wilson 95 % du hit rate AI Picks : **4,98 % – 34,6 %**.

---

## 2. Scope

| Contrôle | Valeur |
| --- | --- |
| Question | Pourquoi 21 / 14,29 % / −32,3 % alors que Elo et Value argmax font 52,94 % ? |
| Univers | 17 matchs Premier League + Ligue 1, 21–24 août 2026, identités déjà labellisées |
| Hors scoring | Paris FC (`19715629`, `isolated_team`) ; Rennes/PSG (`19715631`, exclusion labellisée `inverted_home_away`) |
| Données | Run persisté réel (1011 snapshots weekend, 944 sur les 17 cibles) |
| Interdit ici | tuner, recalibrer, changer de book, choisir un autre snapshot, split TRAIN/OOS, backfill, promouvoir |

Couches lues, non modifiées : Elo candidate, Prediction Service, Odds Service (last-complete PIT), Historical Odds, Value Engine 0.1, AI Picks 0.1, `strategy_metrics` / settlement.

Quality gates locales (cette branche, documentation seule) : `verify:api` 585 passed ; `verify:ingestion` 159 passed ; `verify:ml` 29 passed ; `verify:openapi` + `verify:web` 283 passed + build ; équivalent `verify:all` **PASS**. Aucun secret. Aucune donnée live dans les tests déterministes.

---

## 3. Source Data

Sources utilisées, dans cet ordre :

1. `docs/qa/historical-odds-value-ai-picks-pilot.md` — rapport du run.
2. `workers/ingestion/var/persisted-weekend-score.json` — sortie réelle de `python -m app.backtesting persisted-weekend` (gitignoré via `var/` ; les chiffres reconstruits ci-dessous en sont extraits).
3. Code : `apps/api/app/ai_picks/service.py`, `apps/api/app/ai_picks/config.py`, `docs/ai-picks/ai-picks-v0.1.md`, `apps/api/app/value_engine/calculator.py`, `apps/api/app/odds/service.py`, `apps/api/app/backtesting/persisted.py`, `apps/api/app/backtesting/pilot.py` (`_settle_picks`, `_settle_argmax`), `workers/ml/src/predicta_ml/backtesting/value_metrics.py`, `workers/ml/src/predicta_ml/models/elo.py`.

Métadonnées du run scoring :

| Champ | Valeur |
| --- | --- |
| `kind` | `persisted_live_weekend` |
| `model_version` | `football-elo-v1-candidate` |
| `model_status` | `candidate` |
| `value_engine_version` | `value-engine-0.1` |
| `ai_picks_version` | `ai-picks-0.1` |
| `source` | `the-odds-api-v4` |
| `data_mode` | `live` (persist ; absent des lignes `rows` du JSON, présent dans le run d'ingestion) |
| Seuils | `min_edge=0`, `min_ev=0`, `min_p=0`, `max_odds_age=86400 s`, `optimized_on_test=false` |
| Stake | 1 unité par opportunité (`fixed_unit_per_opportunity`) |
| PIT / Value parity / AI Picks parity / reproductibilité | PASS dans le JSON |

Aucune donnée synthétique n'a remplacé ce run. Les outcomes sont les labels parquet `target` recopiés dans `rows[].outcome`. Cette analyse n'a pas recroisé un feed de scores externe.

---

## 4. Pick Count Reconciliation

### 4.1 Pourquoi 21 picks pour 17 matchs ?

AI Picks 0.1 évalue **les trois issues 1X2** de chaque match, pas seulement l'argmax. Une issue est éligible si EV ≥ 0, edge ≥ 0, P(modèle) ≥ 0 et âge des cotes ≤ 24 h.

Comptage fermé :

```text
17 matchs × 3 sélections = 51
21 éligibles (EV ≥ 0)
30 exclusions `negative_ev`
0 stale_odds
0 invalid_odds
21 + 30 = 51
```

Les 30 exclusions du JSON correspondent exactement aux 30 issues à EV négatif. Aucune issue n'est silencieuse.

### 4.2 Sélections par match

| Picks / match | n matchs | Matchs |
| ---: | ---: | --- |
| 0 | 1 | Everton vs Crystal Palace (`19722201`) — HOME/DRAW/AWAY tous EV < 0 |
| 1 | 11 | voir table pick-by-pick |
| 2 | 5 | Hull, Arsenal, Manchester City, Lens, Marseille |
| 3 | 0 | — |
| **Total** | **17** | **21 picks** |

Les 5 doubles :

| Match | Picks simultanés | Argmax Elo | Issue réelle |
| --- | --- | --- | --- |
| Hull City vs Manchester United | HOME + DRAW | AWAY | HOME |
| Arsenal vs Coventry City | AWAY + DRAW | HOME | HOME |
| Manchester City vs AFC Bournemouth | AWAY + DRAW | HOME | HOME |
| Lens vs Auxerre | AWAY + DRAW | HOME | HOME |
| Olympique Marseille vs Strasbourg | AWAY + DRAW | HOME | HOME |

Quatre doubles sont DRAW+AWAY contre un favori HOME qui gagne (8 unités perdues). Hull est HOME+DRAW ; HOME gagne (+8,20) et DRAW perd (−1,00), net match **+7,20 u** pour **2 u** de mise.

### 4.3 Conformité spécification

`docs/ai-picks/ai-picks-v0.1.md` :

> AI Picks produit ensuite au plus une ligne par `match/market/selection`.

Le ranking inclut `match_id` puis `selection` comme derniers tie-breakers, ce qui n'a de sens que si deux sélections du **même** match peuvent coexister. **Comportement conforme à AI Picks 0.1.** Ce n'est pas un bug. Ce n'est pas non plus une obligation de n'avoir qu'un pick par match.

Everton à 0 pick est également conforme : les trois EV sont négatifs (HOME −0,0072, DRAW −0,0965, AWAY −0,0739). L'argmax Elo était HOME et a gagné ; AI Picks n'a pas pris ce favori.

---

## 5. Mathematical Reconstruction

### 5.1 Formules (moteur, non modifiées)

```text
implied_probability = 1 / odds
overround            = Σ implied_probability          # somme, pas (somme − 1)
no_vig_probability   = implied_probability / overround
edge                 = model_probability − implied_probability
EV                   = model_probability × odds − 1
opportunity_score    = EV + Edge
profit               = (odds − 1) si hit, sinon −1     # mise 1 u
ROI                  = Σ profit / (n_picks × 1)
hit_rate             = hits / n_picks
```

Pour odds > 1, `EV ≥ 0` ⇔ `edge ≥ 0`. Sur les 51 issues, aucun désaccord de signe EV/edge. Les deux seuils V0.1 à 0 sont redondants sur ce marché. Constat descriptif, pas une proposition de fusion.

### 5.2 Headline — reconstruction vs JSON

| Métrique | Rapport QA | JSON scoring | Reconstruction indépendante | Écart |
| --- | ---: | ---: | ---: | --- |
| n | 21 | 21 | 21 | 0 |
| Hits | 3 | 3 | 3 | 0 |
| Hit rate | 14,29 % | 3/21 = 0,142857… | 0,142857… | 0 |
| Profit | −6,78 u | −6,780000000000001 | −6,780000000000001 | 0 |
| ROI | −32,3 % / −32,29 % | −0,322857… | −0,322857… | 0 |
| Drawdown | 9,98 u / **39,0 %** | 9,98 u / **47,52 %** | 9,98 u / **47,52 %** | doc QA |

Détail des 3 hits :

| Pick | Cote | Profit = cote − 1 |
| --- | ---: | ---: |
| Hull HOME | 9,20 | +8,20 |
| Brentford HOME | 2,12 | +1,12 |
| Toulouse AWAY | 2,90 | +1,90 |
| **Somme hits** | | **+11,22** |
| 18 misses | | **−18,00** |
| **Net** | | **−6,78** |
| ROI | −6,78 / 21 | **−32,29 %** |

Le hit rate et le ROI sont **par pick**, pas par match. Chaque pick a la même mise théorique de 1 unité. Un match à 2 picks contribue **2 unités** au dénominateur du ROI.

Drawdown : equity ordonnée par `(kickoff_at, match_id, selection)`. Pic 3,20 u après Hull HOME ; fin −6,78 u ; max drawdown 9,98 u. La formule moteur est `drawdown / (n × stake) = 9,98 / 21 = 47,52 %`. Le « 39,0 % » du rapport source n'est **pas** reproductible. C'est un écart de documentation, pas une erreur du JSON de scoring. Le moteur n'a pas été « corrigé ».

### 5.3 Parité des formules sur les 21 picks

Pour chaque pick, implied, no-vig, edge et EV stockés ont été recalculés depuis odds + probabilités modèle. **0 écart au-delà de 10⁻¹².** Somme des no-vig HOME+DRAW+AWAY = 1 sur les 17 matchs. Somme des probabilités modèle = 1. Ranking `opportunity_score, EV, edge, match_id, selection` reproduit les rangs 1…21.

### 5.4 Attente modèle vs réalisé (descriptif)

Si les 21 P(modèle) étaient calibrées et indépendantes :

| Grandeur | Valeur |
| --- | ---: |
| Σ P(modèle) = hits attendus | 6,81 |
| Hits observés | 3 |
| P moyenne des picks | 32,45 % |
| Hit rate observé | 14,29 % |
| Σ EV = profit attendu si le modèle est vrai | +8,32 u |
| Profit observé | −6,78 u |
| Écart-type binomial approx. des hits | 2,10 |

3 hits vs 6,81 attendus ≈ −1,8 σ. Ce n'est **pas** une preuve de bug ; ce n'est **pas** non plus une preuve de mauvaise calibration. Variance compatible avec n = 21.

---

## 6. Model vs Value vs AI Picks

Trois couches distinctes. Ne pas les conflater.

| Couche | Définition réelle dans ce run | n | Hits | Hit rate | ROI théorique | HOME / DRAW / AWAY |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| **A. Elo argmax** | `max(P_home, P_draw, P_away)` — 1 ligne / match ; `model_performance` | 17 | 9 | 52,94 % | n/a (ce n'est pas un ROI) | 13 / 0 / 4 |
| **B. Value (scoring)** | **le même argmax**, settlé sur la cote PIT — `elo_no_value_filter` | 17 | 9 | 52,94 % | **−5,47 %** | 13 / 0 / 4 |
| **C. AI Picks** | toutes issues EV ≥ 0 — plusieurs lignes possibles / match | 21 | 3 | 14,29 % | **−32,29 %** | 8 / 5 / 8 |

Point critique : le « 52,94 % Value » du rapport source **n'est pas** « meilleure EV ». C'est Elo argmax **sans** filtre Value. D'où l'égalité A = B en hit rate.

### 6.1 AI Picks ≠ Elo argmax (mesuré)

| Relation pick vs argmax | n | Hits |
| --- | ---: | ---: |
| Pick = argmax | 6 | 1 (Brentford HOME) |
| Pick ≠ argmax | 15 | 2 (Hull HOME, Toulouse AWAY) |

Les 6 picks = argmax sont exactement les 6 matchs dont l'argmax a **EV ≥ 0** : Forest HOME, Ipswich AWAY, Brentford HOME, Le Mans HOME, Newcastle HOME, Fulham HOME. Les 11 autres argmax ont EV < 0 ; AI Picks les abandonne.

### 6.2 Mécanisme observé

Les favoris à cote courte (1,22–2,25) portent souvent un EV négatif à cause de l'overround, même quand Elo les élit. AI Picks 0.1, avec `min_ev=0`, **préfère l'outsider / le DRAW à EV positif**. Sur ce weekend, 8 des 9 hits Elo étaient des argmax à EV négatif que AI Picks n'a pas suivis (Marseille, Arsenal, Everton, Lens, Angers, Manchester City, Brighton, Le Havre). Un seul hit Elo est aussi un hit AI Picks (Brentford).

Ce n'est pas un dysfonctionnement démontré du ranking. C'est le filtre d'éligibilité V0.1 appliqué à un modèle dont l'argmax est souvent le favori marché.

---

## 7. Edge Analysis

Tranches **descriptives**. Elles ne proposent aucun nouveau seuil.

| Edge | n | Hits | Hit rate | EV moyen | ROI |
| --- | ---: | ---: | ---: | ---: | ---: |
| < 5 % | 8 | 2 | 25,0 % | 0,090 | −37,3 % |
| 5–10 % | 10 | 0 | 0 % | 0,449 | −100 % |
| 10–20 % | 2 | 0 | 0 % | 0,454 | −100 % |
| 20–30 % | 1 | 1 | 100 % | 2,201 | +820 % |
| > 30 % | 0 | — | — | — | — |

Le seul pick d'edge > 20 % est Hull HOME (edge 23,93 %, cote 9,20), qui gagne. Les 10 picks d'edge 5–10 % sont tous perdants, y compris Arsenal AWAY (cote 16,0). **n trop faible pour en tirer une règle d'edge.**

---

## 8. EV Analysis

Distribution EV des 21 picks : min 0,009 ; médiane 0,246 ; max 2,201.

| EV | n | Hits | Hit rate | Odds moy. | P(modèle) moy. | ROI |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 0–0,15 (faible) | 6 | 2 | 33,3 % | 3,18 | 35,7 % | −16,3 % |
| 0,15–0,40 (moyen) | 9 | 0 | 0 % | 4,20 | 32,3 % | −100 % |
| 0,40–1,00 (élevé) | 4 | 0 | 0 % | 5,23 | 31,6 % | −100 % |
| ≥ 1,00 (très élevé) | 2 | 1 | 50 % | 12,60 | 25,1 % | +360 % |

Les deux EV ≥ 1 sont Arsenal AWAY (EV 1,46, miss, cote 16,0) et Hull HOME (EV 2,20, hit, cote 9,20). Les mauvais résultats **ne sont pas concentrés uniquement** sur les très gros EV : 13 misses sont dans EV 0,15–1,00. Les 2 hits hors Hull sont au contraire des **EV faibles** (0,047 et 0,058).

EV moyen des 21 picks = +0,396 alors que le ROI réalisé = −0,323. Coexistence attendue à petit n : l'EV est une espérance modèle, pas un résultat.

---

## 9. Odds Analysis

Question : AI Picks perd-il surtout parce qu'il sélectionne des événements à forte cote ?

| Cote | n | Hits | Hit rate | ROI | P(modèle) moy. | Edge moy. | EV moy. |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| < 1,50 | 0 | — | — | — | — | — | — |
| 1,50–2,00 | 0 | — | — | — | — | — | — |
| 2,00–3,00 | 5 | 2 | 40,0 % | +0,4 % | 44,4 % | 0,041 | 0,104 |
| 3,00–5,00 | 11 | 0 | 0 % | −100 % | 31,3 % | 0,061 | 0,245 |
| ≥ 5,00 | 5 | 1 | 20,0 % | +84,0 % | 23,1 % | 0,108 | 1,022 |

**Aucun pick AI Picks n'a une cote < 2,00.** L'argmax Elo en a plusieurs (Arsenal 1,22, Hull AWAY 1,36, Lens 1,42, City 1,44, Marseille 1,75, Angers AWAY 1,82, Le Havre AWAY 1,95). Cote moyenne AI Picks **4,90** vs argmax **2,15**.

Sur cet échantillon, 11/21 picks sont dans 3,00–5,00 et font 0/11. C'est compatible avec « plus de longues cotes, plus de misses », **sans** établir que les longues cotes sont la cause unique : le filtre EV élimine précisément les cotes courtes à EV négatif. n = 21.

---

## 10. HOME / DRAW / AWAY

Issues réelles sur les 17 matchs scorés : HOME 9, DRAW 3, AWAY 5.

### 10.1 AI Picks

| Issue | n | Hits | Hit rate | ROI | Odds moy. | P(modèle) moy. | Edge moy. | EV moy. |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| HOME | 8 | 2 | 25,0 % | **+41,5 %** | 4,02 | 39,7 % | 0,094 | 0,508 |
| DRAW | 5 | 0 | 0 % | **−100 %** | 5,04 | 24,6 % | 0,039 | 0,218 |
| AWAY | 8 | 1 | 12,5 % | **−63,8 %** | 5,70 | 30,1 % | 0,060 | 0,396 |

### 10.2 Elo argmax

| Issue | n | Hits | Hit rate | ROI settlé |
| --- | ---: | ---: | ---: | ---: |
| HOME | 13 | 7 | 53,8 % | −5,4 % |
| DRAW | 0 | — | — | — |
| AWAY | 4 | 2 | 50,0 % | −5,8 % |

Elo n'élit **aucun DRAW** comme argmax (P(DRAW) typiquement 0,21–0,28, toujours inférieure à HOME ou AWAY). AI Picks introduit **5 DRAW**, tous perdants. Ce n'est pas classé comme bug : le DRAW entre dès que `P_draw > 1/odds_draw`. Les 3 vrais nuls du weekend (Nice–Lorient, Le Mans–Brest, Newcastle–Liverpool) n'ont **aucun** pick DRAW gagnant : Nice DRAW était EV− ; Le Mans DRAW EV− ; Newcastle DRAW EV−. Les 5 DRAW retenus étaient sur des matchs qui n'ont pas fini nul.

L'introduction de DRAW par Value/AI Picks est **attendue** sous `min_ev=0`. Elle n'est pas, à elle seule, une anomalie logique.

---

## 11. Competition Analysis

| Compétition | Matchs | Picks | Hits | Hit rate | ROI | EV moy. | Edge moy. | Odds moy. |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Premier League | 10 | 12 | 2 | 16,7 % | −5,7 % | 0,544 | 0,083 | 5,50 |
| Ligue 1 | 7 | 9 | 1 | 11,1 % | −67,8 % | 0,200 | 0,047 | 4,10 |

Ligue 1 : 1 hit (Toulouse AWAY) et 8 misses, dont 4 issus des doubles Marseille et Lens. **Aucun écart de compétition n'est interprétable** à n = 9 et n = 12.

Bookmakers PIT (last-complete, pas le « meilleur » EV) :

| Bookmaker | n picks | Hits | Hit rate | ROI | Odds moy. |
| --- | ---: | ---: | ---: | ---: | ---: |
| betsson | 5 | 2 | 40 % | +126 % | 4,22 |
| winamax_fr | 5 | 1 | 20 % | −42 % | 4,00 |
| williamhill | 4 | 0 | 0 % | −100 % | 4,55 |
| coolbet | 2 | 0 | 0 % | −100 % | 11,63 |
| pinnacle | 2 | 0 | 0 % | −100 % | 4,41 |
| nordicbet | 2 | 0 | 0 % | −100 % | 4,05 |
| winamax_de | 1 | 0 | 0 % | −100 % | 3,45 |

Sept bookmakers. Politique inchangée : dernier snapshot 1X2 complet `available_at ≤ kickoff`. Betsson concentre Hull et Brentford (2 des 3 hits). **Aucun changement de bookmaker n'a été évalué pour « améliorer » le ROI.** n par book trop petit.

Provider unique : `the-odds-api-v4`.

---

## 12. Odds Freshness

Seuil AI Picks : 24 h. `stale_odds = 0`. Âge = `kickoff − available_at`. Tous les `available_at` des 17 cibles sont **strictement antérieurs** au coup d'envoi.

| Univers | min | moyenne | médiane | max |
| --- | ---: | ---: | ---: | ---: |
| 17 matchs | 0,073 h (Angers, 264 s) | 1,71 h | 2,32 h | **5,08 h** (Brentford, 18 277 s) |
| 21 picks | 0,073 h | 1,28 h | 0,079 h | 5,08 h |

La médiane des picks est basse parce que les doubles (Marseille, Arsenal, Hull, City, Lens) sont sur des snapshots ~5 minutes avant le premier coup d'envoi du slot.

| Âge | n picks | Hits | ROI |
| --- | ---: | ---: | ---: |
| < 0,25 h | 13 | 1 | −29,2 % |
| 0,25–2 h | 0 | — | — |
| 2–4 h | 7 | 1 | −58,6 % |
| ≥ 4 h | 1 | 1 | +112 % (Brentford, max du run) |

Pas de gradient exploitable. Le pick le plus « stale » du run (5,08 h) est un **hit**. Aucune optimisation de `maximum_odds_age`.

---

## 13. Model Probability Analysis

### 13.1 Picks AI Picks seuls

| P(modèle) | n | Hits | Hit rate | ROI |
| --- | ---: | ---: | ---: | ---: |
| < 20 % | 1 | 0 | 0 % | −100 % (Arsenal AWAY 15,4 %, cote 16,0) |
| 20–30 % | 9 | 0 | 0 % | −100 % |
| 30–40 % | 6 | 2 | 33,3 % | +102 % |
| 40–50 % | 5 | 1 | 20,0 % | −57,6 % |
| > 50 % | 0 | — | — | — |

**Aucun pick AI Picks n'a P(modèle) > 50 %.** Les trois argmax Elo > 50 % (Arsenal 63,2 %, Lens 56,4 %, City 51,2 %) ont tous EV < 0 et sont exclus.

### 13.2 Calibration descriptive — 51 issues (17 matchs × 3)

| Bin P(modèle) | n issues | P moyenne | Fréquence observée |
| --- | ---: | ---: | ---: |
| < 20 % | 1 | 15,4 % | 0 % |
| 20–30 % | 26 | 26,0 % | 19,2 % |
| 30–40 % | 11 | 35,9 % | 36,4 % |
| 40–50 % | 10 | 44,3 % | 50,0 % |
| > 50 % | 3 | 56,9 % | 100 % |

L'ordre est monotone. Les effectifs sont trop petits pour conclure à une mauvaise calibration. **Aucun recalibrage n'a été fait.** Anomalie de calibration : **non établie**.

---

## 14. Pick-by-Pick Analysis

Versions communes à toutes les lignes : `football-elo-v1-candidate` / `value-engine-0.1` / `ai-picks-0.1` / `data_mode=live` / source `the-odds-api-v4`. Exclusion AI Picks : aucune (les 21 sont éligibles). `value selection` = issue de plus grand EV du match (tie-break edge, nom).

### Identité, résultat, cote, PIT

| Rk | Match (UTC) | Comp. | Sélection | Réel | Hit | Cote | Book | `available_at` UTC | Âge |
| ---: | --- | --- | --- | --- | --- | ---: | --- | --- | ---: |
| 1 | Hull City vs Manchester United — 22/08 11:30 | PL | HOME | HOME | hit | 9,20 | betsson | 22/08 11:25:23 | 0,08 h |
| 2 | Arsenal vs Coventry City — 21/08 19:00 | PL | AWAY | HOME | miss | 16,00 | coolbet | 21/08 18:55:29 | 0,08 h |
| 3 | Arsenal vs Coventry City — 21/08 19:00 | PL | DRAW | HOME | miss | 7,25 | coolbet | 21/08 18:55:29 | 0,08 h |
| 4 | Manchester City vs AFC Bournemouth — 23/08 13:00 | PL | AWAY | HOME | miss | 6,50 | williamhill | 23/08 12:55:34 | 0,07 h |
| 5 | Newcastle United vs Liverpool — 23/08 15:30 | PL | HOME | DRAW | miss | 3,70 | williamhill | 23/08 12:55:34 | 2,57 h |
| 6 | Fulham vs Chelsea — 24/08 19:00 | PL | HOME | AWAY | miss | 3,45 | winamax_de | 24/08 18:55:28 | 0,08 h |
| 7 | Angers SCO vs LOSC Lille — 23/08 13:00 | L1 | HOME | AWAY | miss | 4,83 | pinnacle | 23/08 12:55:36 | 0,07 h |
| 8 | Le Havre vs Monaco — 23/08 15:15 | L1 | HOME | AWAY | miss | 3,99 | pinnacle | 23/08 12:55:36 | 2,32 h |
| 9 | Lens vs Auxerre — 22/08 15:15 | L1 | AWAY | HOME | miss | 6,75 | winamax_fr | 22/08 15:10:17 | 0,08 h |
| 10 | Ipswich Town vs Sunderland — 22/08 14:00 | PL | AWAY | HOME | miss | 2,65 | betsson | 22/08 11:25:23 | 2,58 h |
| 11 | Olympique Marseille vs Strasbourg — 21/08 18:45 | L1 | AWAY | HOME | miss | 4,25 | nordicbet | 21/08 18:40:17 | 0,08 h |
| 12 | Hull City vs Manchester United — 22/08 11:30 | PL | DRAW | HOME | miss | 4,80 | betsson | 22/08 11:25:23 | 0,08 h |
| 13 | Brighton vs Aston Villa — 23/08 13:00 | PL | AWAY | HOME | miss | 3,40 | williamhill | 23/08 12:55:34 | 0,07 h |
| 14 | Le Mans vs Brest — 22/08 18:45 | L1 | HOME | DRAW | miss | 2,50 | winamax_fr | 22/08 15:10:17 | 3,58 h |
| 15 | Manchester City vs AFC Bournemouth — 23/08 13:00 | PL | DRAW | HOME | miss | 4,60 | williamhill | 23/08 12:55:34 | 0,07 h |
| 16 | Lens vs Auxerre — 22/08 15:15 | L1 | DRAW | HOME | miss | 4,70 | winamax_fr | 22/08 15:10:17 | 0,08 h |
| 17 | Nice vs Lorient — 22/08 18:45 | L1 | AWAY | DRAW | miss | 3,15 | winamax_fr | 22/08 15:10:17 | 3,58 h |
| 18 | Olympique Marseille vs Strasbourg — 21/08 18:45 | L1 | DRAW | HOME | miss | 3,85 | nordicbet | 21/08 18:40:17 | 0,08 h |
| 19 | Toulouse vs Olympique Lyonnais — 22/08 18:45 | L1 | AWAY | AWAY | hit | 2,90 | winamax_fr | 22/08 15:10:17 | 3,58 h |
| 20 | Brentford vs Tottenham Hotspur — 22/08 16:30 | PL | HOME | HOME | hit | 2,12 | betsson | 22/08 11:25:23 | 5,08 h |
| 21 | Nottingham Forest vs Leeds United — 22/08 14:00 | PL | HOME | AWAY | miss | 2,35 | betsson | 22/08 11:25:23 | 2,58 h |

`match_id` : `mth_football-sportmonks-` + `19722202, 19722203, 19722203, 19722196, 19722195, 19722194, 19715637, 19715636, 19715634, 19722200, 19715633, 19722202, 19722197, 19715635, 19722196, 19715634, 19715632, 19715633, 19715630, 19722198, 19722199`.

### Probabilités, Value, comparaison modèle

| Rk | P(modèle) | Implied | No-vig | Edge | EV | Score | Argmax | Max-EV match | = argmax |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- | --- |
| 1 | 0,3480 | 0,1087 | 0,1033 | 0,2393 | 2,2013 | 2,4406 | AWAY | HOME | non |
| 2 | 0,1540 | 0,0625 | 0,0613 | 0,0915 | 1,4647 | 1,5563 | HOME | AWAY | non |
| 3 | 0,2144 | 0,1379 | 0,1352 | 0,0764 | 0,5541 | 0,6305 | HOME | AWAY | non |
| 4 | 0,2368 | 0,1538 | 0,1444 | 0,0829 | 0,5390 | 0,6219 | HOME | AWAY | non |
| 5 | 0,3953 | 0,2703 | 0,2522 | 0,1250 | 0,4626 | 0,5876 | HOME | HOME | oui |
| 6 | 0,4188 | 0,2899 | 0,2705 | 0,1289 | 0,4448 | 0,5737 | HOME | HOME | oui |
| 7 | 0,2886 | 0,2070 | 0,2009 | 0,0816 | 0,3940 | 0,4756 | AWAY | HOME | non |
| 8 | 0,3392 | 0,2506 | 0,2435 | 0,0886 | 0,3535 | 0,4421 | AWAY | HOME | non |
| 9 | 0,2002 | 0,1481 | 0,1391 | 0,0520 | 0,3513 | 0,4033 | HOME | AWAY | non |
| 10 | 0,4737 | 0,3774 | 0,3587 | 0,0963 | 0,2553 | 0,3516 | AWAY | AWAY | oui |
| 11 | 0,2931 | 0,2353 | 0,2206 | 0,0578 | 0,2456 | 0,3034 | HOME | AWAY | non |
| 12 | 0,2517 | 0,2083 | 0,1980 | 0,0434 | 0,2082 | 0,2515 | AWAY | HOME | non |
| 13 | 0,3473 | 0,2941 | 0,2740 | 0,0532 | 0,1808 | 0,2340 | HOME | AWAY | non |
| 14 | 0,4607 | 0,4000 | 0,3750 | 0,0607 | 0,1518 | 0,2125 | HOME | HOME | oui |
| 15 | 0,2517 | 0,2174 | 0,2040 | 0,0343 | 0,1578 | 0,1921 | HOME | AWAY | non |
| 16 | 0,2354 | 0,2128 | 0,1998 | 0,0226 | 0,1063 | 0,1290 | HOME | AWAY | non |
| 17 | 0,3407 | 0,3175 | 0,2953 | 0,0233 | 0,0733 | 0,0965 | HOME | AWAY | non |
| 18 | 0,2762 | 0,2597 | 0,2436 | 0,0165 | 0,0635 | 0,0800 | HOME | AWAY | non |
| 19 | 0,3648 | 0,3448 | 0,3224 | 0,0200 | 0,0579 | 0,0779 | HOME | AWAY | non |
| 20 | 0,4940 | 0,4717 | 0,4465 | 0,0223 | 0,0472 | 0,0694 | HOME | HOME | oui |
| 21 | 0,4294 | 0,4255 | 0,4050 | 0,0039 | 0,0090 | 0,0129 | HOME | HOME | oui |

Rang 14 (Le Mans HOME, score 0,2125) passe avant rang 15 (City DRAW, 0,1921) : conforme au tri par score. Aucune inversion de ranking détectée.

---

## 15. Error Analysis

Pour chaque miss, uniquement les grandeurs observées. Pas d'attribution causale (« le modèle s'est trompé parce que… »).

| Match | Pick | P(modèle) | Cote | Edge | EV | Issue observée |
| --- | --- | ---: | ---: | ---: | ---: | --- |
| Arsenal vs Coventry | AWAY | 15,40 % | 16,00 | 9,15 % | 1,465 | HOME |
| Arsenal vs Coventry | DRAW | 21,44 % | 7,25 | 7,64 % | 0,554 | HOME |
| Manchester City vs Bournemouth | AWAY | 23,68 % | 6,50 | 8,29 % | 0,539 | HOME |
| Newcastle vs Liverpool | HOME | 39,53 % | 3,70 | 12,50 % | 0,463 | DRAW |
| Fulham vs Chelsea | HOME | 41,88 % | 3,45 | 12,89 % | 0,445 | AWAY |
| Angers vs Lille | HOME | 28,86 % | 4,83 | 8,16 % | 0,394 | AWAY |
| Le Havre vs Monaco | HOME | 33,92 % | 3,99 | 8,86 % | 0,354 | AWAY |
| Lens vs Auxerre | AWAY | 20,02 % | 6,75 | 5,20 % | 0,351 | HOME |
| Ipswich vs Sunderland | AWAY | 47,37 % | 2,65 | 9,63 % | 0,255 | HOME |
| Marseille vs Strasbourg | AWAY | 29,31 % | 4,25 | 5,78 % | 0,246 | HOME |
| Hull vs Manchester United | DRAW | 25,17 % | 4,80 | 4,34 % | 0,208 | HOME |
| Brighton vs Aston Villa | AWAY | 34,73 % | 3,40 | 5,32 % | 0,181 | HOME |
| Le Mans vs Brest | HOME | 46,07 % | 2,50 | 6,07 % | 0,152 | DRAW |
| Manchester City vs Bournemouth | DRAW | 25,17 % | 4,60 | 3,43 % | 0,158 | HOME |
| Lens vs Auxerre | DRAW | 23,54 % | 4,70 | 2,26 % | 0,106 | HOME |
| Nice vs Lorient | AWAY | 34,07 % | 3,15 | 2,33 % | 0,073 | DRAW |
| Marseille vs Strasbourg | DRAW | 27,62 % | 3,85 | 1,65 % | 0,064 | HOME |
| Forest vs Leeds | HOME | 42,94 % | 2,35 | 0,39 % | 0,009 | AWAY |

Lectures factuelles :

- Sur 18 misses, le modèle assignait entre 15,4 % et 47,4 % à l'issue retenue.
- 8 misses sont des DRAW ou AWAY sur un match dont l'issue observée est HOME (y compris 4 doubles DRAW+AWAY).
- Ipswich AWAY (47,4 %, cote 2,65) est le pick AI Picks de plus haute P(modèle) parmi les misses ; l'issue observée a été HOME.
- Forest HOME (edge 0,39 %, presque EV nul) : l'issue observée a été AWAY.

Hits, pour la même grille :

- Hull HOME : P(modèle) 34,80 % ; issue observée HOME ; cote 9,20.
- Toulouse AWAY : P(modèle) 36,48 % ; issue observée AWAY ; cote 2,90.
- Brentford HOME : P(modèle) 49,40 % ; issue observée HOME ; cote 2,12.

---

## 16. Data / Logic Anomalies

Contrôles demandés :

| # | Contrôle | Résultat |
| ---: | --- | --- |
| 1 | Odds vs implied | PASS (`implied = 1/odds`, résidu ≤ 6×10⁻¹⁷) |
| 2 | No-vig | PASS (simplexe = 1 ; = implied / Σ implied) |
| 3 | Edge | PASS (`P − implied`) |
| 4 | EV | PASS (`P × odds − 1`) |
| 5 | Résultat associé au match | Outcomes JSON = labels parquet du scoring ; pas de recoupement feed externe dans cette branche |
| 6 | HOME/AWAY | Pas de retournement sur les 17 cibles. Paris FC unmatched ; Rennes/PSG hors univers scoring (exclusion labellisée, snapshots persistés non scorés) |
| 7 | Timestamp | `available_at` = `last_update` bookmaker, contrat déjà documenté |
| 8 | Snapshot après cutoff | 0 (tous les âges > 0) |
| 9 | Snapshot trop ancien | 0 au-delà de 24 h ; max 5,08 h |
| 10 | Duplicate snapshot | Non évalué au niveau SQL ici ; le scoring retient 1 last-complete / match. 17 books fingerprint distincts |
| 11 | Duplicate pick | 0 paire `(match_id, selection)` dupliquée |
| 12 | Multiple picks inattendus | 5 doubles, **conformes** à la spec (une ligne / sélection) |
| 13 | Classement | PASS (21/21) |
| 14 | Exclusion | 30 `negative_ev` + 2 identités scoring ; 51 = 21 + 30 |
| 15 | Modèle associé | `football-elo-v1-candidate` partout |
| 16 | Provider | `the-odds-api-v4` unique |
| 17 | `data_mode` | `live` au persist ; non recopié sur chaque `rows[]` du JSON de scoring — absence de champ, pas une contradiction live/mock |
| 18 | Résultat réel incorrect | Non démontré. Les 3 nuls (Nice, Le Mans, Newcastle) et les scores 1X2 utilisés sont ceux du parquet |

Écart documentaire (rapport source, pas le moteur) : drawdown AI Picks « 39,0 % » vs 47,52 % dans le JSON et la formule `max_drawdown_units / n`.

**Aucune anomalie moteur, de données PIT, de parité Value, de ranking ou de logique AI Picks 0.1 n'a été établie.**

---

## 17. Baselines

Descriptives, **même** 17 matchs, cotes PIT identiques. Pas une optimisation.

| Stratégie | n | Hits | Hit rate | ROI théorique | Note |
| --- | ---: | ---: | ---: | ---: | --- |
| Naive HOME | 17 | 9 | 52,94 % | **+42,9 %** | Tirée par Hull 9,20 (+8,20 u). Wilson 95 % : 31,0 % – 73,8 % |
| Elo argmax (settled) | 17 | 9 | 52,94 % | **−5,47 %** | Même hit rate, cotes plus courtes (moy. 2,15) |
| AI Picks 0.1 | 21 | 3 | 14,29 % | **−32,29 %** | Mise 21 u, pas 17 u |

Naive HOME et Elo ont le même hit rate 9/17 sur **cet** échantillon ; le ROI diverge à cause de Hull (naive le prend, Elo argmax prend AWAY à 1,36 et perd). AI Picks prend Hull HOME **et** DRAW.

Cette comparaison **ne justifie pas** de remplacer AI Picks par always-HOME, ni l'inverse.

---

## 18. Statistical Limitations

- n = 17 matchs, n = 21 picks, une seule fenêtre, pas d'OOS, pas de split.
- Wilson 95 % hit rate AI Picks : **5,0 % – 34,6 %**. Le 14,29 % observé est compatible avec une large plage.
- Wilson 95 % Elo/naive 9/17 : **31,0 % – 73,8 %**. Les intervalles AI Picks et Elo se chevauchent à peine en bordure ; ce n'est **pas** un test d'hypothèse formel et ne doit pas être lu comme une preuve.
- Un seul pick (Hull 9,20) pèse +8,20 u sur un P&L de −6,78 u. La métrique est instable.
- 5 matchs comptent double dans le ROI. Comparer 14,29 % (dénominateur 21) à 52,94 % (dénominateur 17) mélange deux unités.

Aucun test sophistiqué n'est rapporté. Objectif : montrer la variance, pas conclure.

---

## 19. Findings

1. **21 / 14,29 % / −32,29 % sont arithmétiquement exacts** (par pick, mise 1 u).
2. **21 > 17** parce que plusieurs issues EV+ par match sont autorisées et observées (5 doubles).
3. **AI Picks ≠ Elo argmax** (15/21 picks différents). Le 52,94 % « Value » du run est l'argmax Elo settlé, pas le ranking AI Picks.
4. Le filtre `EV ≥ 0` écarte 11 favoris modèle à EV négatif, dont 8 hits Elo sur ce weekend.
5. AI Picks n'a **aucune** cote < 2,00 et **aucun** P(modèle) > 50 %. Cote moyenne 4,90.
6. 5 DRAW éligibles, 0 hit DRAW ; Elo n'avait 0 argmax DRAW. Conforme aux formules, non classé bug.
7. 0 anomalie de parité, PIT, ranking, exclusions, duplicates, timestamps post-cutoff.
8. Écart doc : 39,0 % vs 47,52 % de drawdown dans le rapport source.
9. Échantillon insuffisant pour attribuer le P&L au modèle, aux prix, ou à la variance seule.

---

## 20. Recommendation

Cette branche ne recommande **aucun** changement de K, home advantage, calibration, `minimum_edge`, `minimum_ev`, `minimum_model_probability`, `maximum_odds_age`, ranking, bookmaker ou univers.

Pour le prochain agent, les options restent ouvertes et **non tranchées** par n = 21 :

1. **Ne pas corriger un bug** — aucun n'a été identifié dans le moteur.
2. **Collecter davantage de fenêtres** bornées (même cadence, même seuils) avant toute conclusion.
3. **Ne pas tuner** les seuils sur ces 17 matchs.
4. Si une investigation produit est ouverte plus tard, séparer explicitement : (a) qualité de l'argmax Elo, (b) effet du filtre EV≥0 qui remplace les favoris, (c) effet des multi-picks sur le ROI. Ce n'est pas une feuille de route de tuning.
5. Dossier identité Rennes/PSG : rester hors de cette analyse de stratégie.
6. Corriger éventuellement, dans un run doc ultérieur, le pourcentage de drawdown du rapport source (39,0 % → 47,52 %). Hors scope de modification moteur.

---

## 21. Verdict

**NO ANOMALY FOUND**

| Question | Réponse |
| --- | --- |
| A. Bug identifiable ? | **Non.** Ranking, formules, settlement, exclusions et PIT se reconstruisent. |
| B. Anomalie de données ? | **Non établie** sur les 17 cibles (PIT, ages, HOME/AWAY, provider). Rennes/PSG reste une exclusion d'identité labellisée, pas une donnée scorée altérée. |
| C. Anomalie de calcul ? | **Moteur : non.** Hit rate et ROI JSON = reconstruction. **Documentation source :** drawdown 39,0 % vs 47,52 %. |
| D. Anomalie logique AI Picks ? | **Non.** Multi-picks et DRAW EV+ sont dans la spec 0.1. |
| E. Cause principale du mauvais résultat ? | **Impossible à déterminer** comme cause unique. Sur cet échantillon, le P&L coïncide avec (i) le filtre EV qui écarte les favoris à cote courte, (ii) des cotes plus longues, (iii) n = 21. Variance compatible (3 hits vs 6,8 attendus). Pas d'attribution « le modèle est cassé » ou « les prix sont cassés ». |
| F. Information supplémentaire avant de conclure ? | Plus de matchs / fenêtres, **mêmes** règles. Recoupement optionnel des labels `target` avec un feed de scores indépendant. Pas de nouveau seuil. |

`football-elo-v1-candidate` reste candidate. Value Engine 0.1 et AI Picks 0.1 restent inchangés.

**Résultat descriptif, insuffisant pour conclure à une rentabilité — ou à une non-rentabilité — future.**
