# Expanded Value / AI Picks Analysis

**Branche :** `agent/ml/analyze-expanded-value-ai-picks`  
**Nature :** analyse uniquement. Aucun modèle, seuil, ranking, bookmaker ou snapshot n'a été modifié.  
**Run analysé :** `docs/qa/expanded-historical-odds-value-ai-picks-pilot.md`  
**Analyse précédente (n = 17 / 21) :** `docs/qa/value-ai-picks-pilot-analysis.md`  
**Artefact scoring (gitignoré, `var/`) :** `workers/ingestion/var/persisted-expanded-score.json`  
**Modèle :** `football-elo-v1-candidate` — non promu  
**Value Engine :** `value-engine-0.1`  
**AI Picks :** `ai-picks-0.1`  
**Verdict :** **NO ANOMALY FOUND**

**Performance descriptive sur l'échantillon étudié ; insuffisante pour conclure à une rentabilité future.**

Le +8,3 % global **n'existe pas** sur août–septembre / `final_test` (ROI **−10,2 %**). Il est porté par mai / `calibration_select` (ROI **+21,9 %**) et, à l'échelle des 161 picks, par un petit nombre de gagnants à cote longue. Ce n'est **pas** un 119 matchs OOS.

---

## 1. Executive Summary

Reconstruction indépendante depuis les 161 fingerprints + 126 lignes match : **41 hits, profit +13,43 u, ROI +8,34 %**. Écart moteur JSON : **0**. Formules, ranking, PIT, exclusions : **PASS**.

Ce que le +8,3 % n'est pas :

- un signal réparti sur les 161 picks ;
- un résultat `final_test` ;
- un ROI par match ;
- la même chose que les 45,4 % Elo / Value settled.

Ce qu'il est, mesuré :

| Fait | Valeur |
| --- | --- |
| Stake | 1 unité **par pick** (`fixed_unit_per_opportunity`) |
| 161 picks / 119 matchs | 7 × 0 pick, 63 × 1, 49 × 2, 0 × 3 |
| Hors meilleur gagnant (Hull HOME 9,20, +8,20 u) | ROI **+3,27 %** |
| Hors top 2 | ROI **−1,11 %** |
| Hors top 3 | ROI **−5,42 %** |
| Hors top 5 | ROI **−13,87 %** |
| Mai / `calibration_select` | 66 matchs, 93 picks, ROI **+21,9 %**, +20,36 u |
| Août–septembre / `final_test` | 53 matchs, 68 picks, ROI **−10,2 %**, −6,93 u |
| Picks ≠ Elo argmax | 121 / 161, profit **+16,61 u** |
| Picks = Elo argmax | 40 / 161, profit **−3,18 u** |
| AWAY | +17,10 u ; HOME **−5,21 u** ; DRAW +1,54 u |
| Matchs à 2 picks | +27,80 u ; matchs à 1 pick **−14,37 u** |

Wilson 95 % hit rate 161 picks : **19,4 % – 32,7 %**. Un intervalle ROI robuste n'est pas disponible (picks non i.i.d., multi-picks, longues cotes).

Aucune anomalie moteur. Le +8,3 % agrégé est une **observation concentrée et temporellement mixte**, pas une preuve de rentabilité.

---

## 2. Dataset

| Grandeur | n |
| --- | ---: |
| Matchs parquet dans les 3 fenêtres | 126 |
| Identity rejected (ledger) | 7 |
| Identity-matched scorés | **119** |
| Avec cotes PIT 1X2 | 119 / 119 |
| AI Picks éligibles | **161** |
| Issues 1X2 évaluées | 119 × 3 = 357 |
| Exclusions `negative_ev` | 196 |
| Premier League / Ligue 1 | 71 / 48 |
| Issues réelles | HOME 46, DRAW 36, AWAY 37 |

Fenêtres figées **avant** le scoring :

| Fenêtre | Bornes UTC | Fetch | Elo partition |
| --- | --- | --- | --- |
| `end-2025-26-may` | 2026-05-01 → 2026-05-25 | oui | `calibration_select` (2026-05-01 → 2026-07-01) |
| `persist-weekend-2026-08-21` | 2026-08-21 → 2026-08-25 | non (reuse) | `final_test` (≥ 2026-07-01) |
| `2026-27-following-matchweeks` | 2026-08-28 → 2026-09-07 | oui | `final_test` |

Source scoring : `kind=persisted_live_expanded`, `source=the-odds-api-v4`, `data_mode=live`, horloge `2026-09-07T00:00:00Z`. Seuils V0.1 inchangés (`min_edge=0`, `min_ev=0`, `min_p=0`, `max_odds_age=24h`, `optimized_on_test=false`).

Cette analyse n'a pas recréé de cotes ni relancé The Odds API. Les outcomes sont les labels parquet `target`.

Quality gates (documentation seule) : `verify:api` 588 passed ; `verify:ingestion` 167 passed ; `verify:ml` 29 passed ; `verify:openapi` + `verify:web` 283 passed + build ; équivalent `verify:all` **PASS**. Aucun secret. Aucune modification métier.

---

## 3. Temporal Split

**Ne pas lire « 119 matchs OOS ».**

| Univers | Partition Elo | Matchs | Picks | Rôle dans ce rapport |
| --- | --- | ---: | ---: | --- |
| **A. Mai** | `calibration_select` | 66 | 93 | la calibration du candidat a pu voir cette période |
| **B. Août–septembre** | `final_test` | 53 | 68 | hors `calibration_select` (weekend 17 + suivantes 36) |
| **C. Ensemble** | mélange A+B | 119 | 161 | descriptif agrégé uniquement |

Juin 2026 : 0 match terminé dans le dataset 0.3 (trou documenté). `FINAL_TRAIN_END=2026-01-01`, `CALIBRATION_FIT_END=2026-05-01`, `FINAL_TEST_START=2026-07-01` — constantes Elo **non modifiées**.

Le modèle n'a pas été recalibré sur cet élargissement. Mai reste dans la fenêtre où la méthode de calibration a été choisie.

---

## 4. Mathematical Reconstruction

Formules `value-engine-0.1` / settlement, inchangées :

```text
implied = 1 / odds
overround = Σ implied
no_vig = implied / overround
edge = model_probability − implied
EV = model_probability × odds − 1
profit = (odds − 1) si hit sinon −1    # mise 1 u
ROI = Σ profit / n_picks
```

Pour odds > 1, `EV ≥ 0` ⇔ `edge ≥ 0`. Compte fermé : 161 + 196 = 357.

| Métrique | JSON scoring | Reconstruction | Écart |
| --- | ---: | ---: | --- |
| n | 161 | 161 | 0 |
| Hits | 41 | 41 | 0 |
| Hit rate | 25,47 % | 41/161 = 0,254658… | 0 |
| Profit | +13,43 u | +13,429999… | 0 |
| ROI | +8,34 % | +0,083416… | 0 |
| Drawdown | 15,00 u / 9,32 % | 15,00 u / 9,32 % | 0 |
| Cote / edge / EV moyens | 4,99 / +0,060 / +0,335 | identiques | 0 |

Ranking `opportunity_score = EV + Edge` : **161/161 rangs reproduits**. Implied / no-vig / edge / EV : **0 écart > 10⁻⁹**.

41 hits → +133,43 u bruts. 120 misses → −120,00 u. Net **+13,43 u**.

---

## 5. Model vs Value vs AI Picks

Trois univers. Unités différentes.

| Couche | Définition | Unité | n | Hits | Hit rate | ROI |
| --- | --- | --- | ---: | ---: | ---: | --- |
| **Elo argmax** | max P(HOME/DRAW/AWAY), 1 / match | match | 119 | 54 | 45,38 % | n/a (modèle) |
| **Value settled** | **le même argmax**, cote PIT, **sans** filtre EV | match = 1 u | 119 | 54 | 45,38 % | **−13,08 %** (−15,57 u) |
| **AI Picks 0.1** | toutes issues EV ≥ 0 | pick = 1 u | 161 | 41 | 25,47 % | **+8,34 %** (+13,43 u) |
| Naive HOME | toujours HOME | match = 1 u | 119 | 46 | 38,66 % | −14,55 % |

On ne peut pas comparer +8,3 % à −13,1 % comme deux ROI « du même pari ». Le dénominateur passe de 119 u à 161 u. Value settled **n'est pas** « meilleur EV » : c'est `elo_no_value_filter`.

Sur les **mêmes** 119 matchs, l'argmax à cote courte (moyenne 2,07) perd 15,57 u. AI Picks, en sautant 79 argmax à EV négatif et en prenant 161 issues EV+, affiche +13,43 u — **surtout en mai**, voir §17–18.

---

## 6. Pick Distribution

| | HOME | DRAW | AWAY |
| --- | ---: | ---: | ---: |
| Elo / Value argmax | 93 | 0 | 26 |
| AI Picks | 55 | 54 | 52 |
| Issues réelles (119) | 46 | 36 | 37 |

AI Picks est quasi uniforme sur les 3 issues. Elo n'élit **aucun DRAW**. 40 picks = argmax (exactement les 40 argmax à EV ≥ 0) ; 121 picks ≠ argmax.

Cote moyenne : AI Picks 4,99 vs argmax 2,07. P(modèle) moyenne des picks : 30,3 %.

---

## 7. Odds Distribution

Tranches **descriptives**. Pas un nouveau filtre.

| Cote | n | Hits | Hit rate | Profit | ROI | P(modèle) moy. | Edge moy. | EV moy. |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| < 2,00 | 2 | 2 | 100 % | +1,58 | +79,0 % | 57,3 % | 0,012 | 0,022 |
| 2,00–3,00 | 26 | 9 | 34,6 % | −3,66 | −14,1 % | 44,9 % | 0,048 | 0,123 |
| 3,00–5,00 | 77 | 21 | 27,3 % | +8,70 | +11,3 % | 30,0 % | 0,050 | 0,199 |
| 5,00–10,00 | 51 | 9 | 17,6 % | **+11,81** | +23,2 % | 23,6 % | 0,079 | 0,538 |
| > 10,00 | 5 | 0 | 0 % | −5,00 | −100 % | 16,7 % | 0,095 | 1,586 |

Les 9 hits à cote 5–10 contribuent **+11,81 u** sur un net de +13,43 u. Les 5 picks > 10 (tous AWAY) sont 0/5. Cotes < 5 : +6,62 u (n = 105). Cotes ≥ 5 : +6,81 u (n = 56, hit rate 16,1 %).

Le 25,5 % de hit rate est **compatible** avec une cote moyenne ~5 (implied ~20 %) plus un P(modèle) moyen ~30 %. Ce n'est pas, à soi seul, une anomalie.

Les cellules n = 2 et n = 5 sont du bruit. Elles ne justifient aucun seuil.

---

## 8. Edge Distribution

| Edge | n | Hits | Hit rate | Profit | ROI | Odds moy. | EV moy. |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| < 5 % | 70 | 22 | 31,4 % | **+11,04** | +15,8 % | 4,02 | 0,094 |
| 5–10 % | 66 | 13 | 19,7 % | −5,71 | −8,7 % | 5,91 | 0,446 |
| 10–20 % | 24 | 5 | 20,8 % | −0,10 | −0,4 % | 5,13 | 0,657 |
| 20–30 % | 1 | 1 | 100 % | +8,20 | +820 % | 9,20 | 2,201 |
| > 30 % | 0 | — | — | — | — | — | — |

Le profit n'augmente pas avec l'edge. La tranche < 5 % (surtout DRAW à petite edge) est la plus rentable **sur cet échantillon**, hors le singleton Hull (edge 23,9 %). **Ne pas en faire un `minimum_edge`.**

---

## 9. EV Distribution

Question : le +8,3 % vient-il des plus gros EV ?

| EV | n | Hits | Hit rate | Profit | ROI | Odds moy. | Edge moy. | P(modèle) |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 0–0,15 (faible) | 56 | 20 | 35,7 % | +8,94 | +16,0 % | 3,53 | 0,019 | 32,5 % |
| 0,15–0,40 | 56 | 9 | 16,1 % | **−17,37** | −31,0 % | 4,46 | 0,061 | 30,6 % |
| 0,40–1,00 | 41 | 10 | 24,4 % | +12,86 | +31,4 % | 6,11 | 0,099 | 28,1 % |
| ≥ 1,00 | 8 | 2 | 25,0 % | +9,00 | +112,5 % | 13,14 | 0,136 | 23,2 % |

Non univoque. EV 0,15–0,40 (le « moyen ») est le **pire** P&L. EV ≥ 1 : 2 hits dont Hull et Chelsea AWAY 7,80 ; 6 misses. Le +8,3 % n'est **pas** « les plus gros EV gagnent, le reste suit ».

Σ EV des 161 picks = **+53,97 u** (espérance si le modèle est vrai). Réalisé **+13,43 u**.

---

## 10. HOME / DRAW / AWAY

| Issue | AI Picks n | Hits | Hit rate | Profit | ROI | Odds moy. | P(modèle) | Edge | EV |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| HOME | 55 | 15 | 27,3 % | **−5,21** | −9,5 % | 3,69 | 39,2 % | 0,082 | 0,355 |
| DRAW | 54 | 12 | 22,2 % | +1,54 | +2,9 % | 4,84 | 24,8 % | 0,033 | 0,184 |
| AWAY | 52 | 14 | 26,9 % | **+17,10** | +32,9 % | 6,52 | 26,5 % | 0,064 | 0,472 |

Elo/Value argmax : HOME 93 (41 hits, ROI −14,0 %), AWAY 26 (13 hits, ROI −9,9 %), DRAW 0.

Le P&L AI Picks est **porté par AWAY** (cotes moyennes 6,52). HOME, malgré Hull +8,20, reste net négatif. Ce n'est pas une promotion d'une stratégie « always AWAY ».

---

## 11. Premier League vs Ligue 1

| | Premier League | Ligue 1 |
| --- | ---: | ---: |
| Matchs | 71 | 48 |
| Elo accuracy | 46,5 % | 43,8 % |
| Value ROI | −12,2 % | −14,3 % |
| AI Picks n / hits | 97 / 26 | 64 / 15 |
| AI Picks hit rate | 26,8 % | 23,4 % |
| AI Picks profit / ROI | +5,14 u / +5,3 % | +8,29 u / +13,0 % |
| Odds / edge / EV moy. | 5,06 / 0,061 / 0,359 | 4,88 / 0,057 / 0,299 |

### Croisement ligue × période (AI Picks)

| | Mai `calibration_select` | Août–sept. `final_test` |
| --- | --- | --- |
| PL | 41 matchs, 59 picks, ROI **+18,7 %** (+11,03 u) | 30 matchs, 38 picks, ROI **−15,5 %** (−5,89 u) |
| L1 | 25 matchs, 34 picks, ROI **+27,4 %** (+9,33 u) | 23 matchs, 30 picks, ROI **−3,5 %** (−1,04 u) |

Les deux ligues sont positives en mai et **négatives en `final_test`**. Pas d'effet ligue isolable comme cause du +8,3 % global.

---

## 12. Calibration Probability Analysis

### Picks AI Picks

| P(modèle) | n | Hits | Observé | P moyenne | ROI |
| --- | ---: | ---: | ---: | ---: | ---: |
| < 20 % | 13 | 2 | 15,4 % | 17,0 % | +21,2 % |
| 20–30 % | 86 | 19 | 22,1 % | 25,1 % | +9,3 % |
| 30–40 % | 33 | 8 | 24,2 % | 35,2 % | +3,4 % |
| 40–50 % | 23 | 9 | 39,1 % | 43,8 % | +7,7 % |
| > 50 % | 6 | 3 | 50,0 % | 54,6 % | −4,5 % |

Σ P(modèle) = **48,73 hits attendus** vs **41 observés** (écart ≈ 1,4 σ binomial, σ ≈ 5,71). Pas une preuve de mauvaise calibration des picks.

Les 2 hits à P < 20 % sont Lille–Auxerre AWAY (18,5 %, cote 8,00, mai) et PSG–Monaco AWAY (19,3 %, cote 7,76, septembre). Ils pèsent +13,76 u à eux deux — concentration, pas une classe calibrée.

### 357 issues (descriptif, pas un recalibrage)

| Bin | n | P moy. | Fréquence observée |
| --- | ---: | ---: | ---: |
| < 20 % | 14 | 17,0 % | 14,3 % |
| 20–30 % | 174 | 25,4 % | 28,7 % |
| 30–40 % | 70 | 34,9 % | 27,1 % |
| 40–50 % | 65 | 44,3 % | 43,1 % |
| > 50 % | 34 | 56,5 % | 58,8 % |

Ordre globalement monotone. Le bin 30–40 % est un peu bas (27 % vs 35 %). **Pas de recalibrage.**

Par période, sur les picks : mai E[hits] = 27,76 vs 27 observés ; `final_test` E[hits] = 20,97 vs **14** observés. Le sous-performance août–septembre est aussi un écart à l'espérance **du modèle lui-même**, pas seulement vs Elo.

---

## 13. Multiple Picks per Match

Conforme AI Picks 0.1 (une ligne par `match/marché/sélection`).

| Picks / match | n matchs | n picks | Profit | ROI des picks |
| ---: | ---: | ---: | ---: | ---: |
| 0 | 7 | 0 | 0 | — |
| 1 | 63 | 63 | **−14,37 u** | **−22,8 %** |
| 2 | 49 | 98 | **+27,80 u** | **+28,4 %** |
| 3 | 0 | 0 | — | — |
| Total | 119 | 161 | +13,43 u | +8,34 % |

**Tout le profit net vient des matchs à 2 picks.** Les 63 mono-picks (souvent l'argmax à petit EV+) perdent 14,37 u. Les doubles sont surtout DRAW+AWAY contre un favori HOME (cotes plus longues, mise 2 u / match).

Les 7 matchs à 0 pick ont les 3 EV négatifs (ex. Liverpool–Chelsea 9 mai, Everton–Palace 22 août). Deux de ces argmax Elo ont gagné (Auxerre–Nice, Lens–PSG, Everton–Palace). Conforme au filtre EV, pas une suppression.

---

## 14. P&L Curve

Ordre : `(kickoff_at, match_id, selection)`. Mise 1 u / pick.

| Jalon | Date UTC | Equity | Commentaire |
| --- | --- | ---: | --- |
| Premier pick | 2026-05-01 19:00 | −1,00 | Leeds AWAY miss |
| Plus bas | (parcours mai) | **−8,69** | creux précoce |
| Fin mai (`calibration_select`) | après 93 picks | **+20,36** | tout le profit agrégé est déjà là |
| Fin weekend 21–24 août | +21 picks | +13,58 | les 21 picks du premier pilote : −6,78 |
| Pic | 2026-08-30 13:00 | **+26,24** | Sunderland HOME hit à 2,30 |
| Max DD atteint | 2026-09-04 19:00 | +11,24 | Ipswich HOME miss ; DD = 15,00 depuis le pic |
| Fin suivantes | 2026-09-06 | **+13,43** | last pick Arsenal HOME hit 1,68 |

Par mois civil : mai +20,36 u (93) ; août −4,12 u (46) ; septembre −2,81 u (22).

---

## 15. Drawdown

| | Reconstruction | JSON moteur |
| --- | ---: | ---: |
| Peak | 26,24 u (30 août, Sunderland HOME) | — |
| Equity au max DD | 11,24 u | — |
| Max drawdown | **15,00 u** | 15,00 u |
| DD / stake cumulé | 15 / 161 = **9,32 %** | 9,32 % |
| P&L final | +13,43 u | +13,43 u |

Cohérent. Le rapport d'expansion source donne les mêmes 15,00 u / 9,32 %. Pas d'écart documentaire sur le drawdown de ce run (contrairement au 39 % vs 47,5 % du premier pilote de 21 picks).

Un DD de 15 u sur un net de 13 u illustre la variance des longues cotes. Ce n'est pas une preuve de robustesse, ni un bug.

Value settled : DD 19,20 u / 16,1 % pour un P&L de −15,57 u.

---

## 16. Profit Concentration

Gagnants officiels **conservés**. Leave-out = diagnostic, pas un nouveau résultat.

| Ensemble | n | Profit | ROI |
| --- | ---: | ---: | ---: |
| Officiel (161) | 161 | +13,43 | **+8,34 %** |
| Hors top 1 | 160 | +5,23 | +3,27 % |
| Hors top 2 | 159 | −1,77 | **−1,11 %** |
| Hors top 3 | 158 | −8,57 | −5,42 % |
| Hors top 5 | 156 | −21,63 | −13,87 % |

Top 5 gagnants (26,3 % du brut +133,43 u ; **261 % du net** parce que les losers existent) :

| # | Match | Date | Pick | Cote | Profit | Période |
| ---: | --- | --- | --- | ---: | ---: | --- |
| 1 | Hull City vs Manchester United | 22 août | HOME | 9,20 | +8,20 | `final_test` |
| 2 | LOSC Lille vs Auxerre | 17 mai | AWAY | 8,00 | +7,00 | `calibration_select` |
| 3 | Chelsea vs Nottingham Forest | 4 mai | AWAY | 7,80 | +6,80 | `calibration_select` |
| 4 | Paris Saint Germain vs Monaco | 4 sept. | AWAY | 7,76 | +6,76 | `final_test` |
| 5 | Manchester City vs Aston Villa | 24 mai | AWAY | 7,30 | +6,30 | `calibration_select` |

Top 1 = 61 % du net. **Sans le 2ᵉ gagnant, le ROI agrégé devient négatif.** Le +8,3 % n'est pas distribué.

Aucun gagnant à cote > 10. Les 9 hits à cote 5–10 suffisent à expliquer l'essentiel du net.

---

## 17. May / Calibration Select

66 matchs (PL 41, L1 25). 93 picks.

| Couche | n | Hits | Hit rate | Profit | ROI |
| --- | ---: | ---: | ---: | ---: | ---: |
| Elo argmax / Value settled | 66 | 31 | 47,0 % | −4,48 | −6,8 % |
| Naive HOME | 66 | 28 | 42,4 % | −5,81 | −8,8 % |
| **AI Picks** | **93** | **27** | **29,0 %** | **+20,36** | **+21,9 %** |

Wilson 95 % hit rate AI Picks mai : **20,8 % – 38,9 %**.

HDA picks : HOME 30, DRAW 34, AWAY 29. Cote moyenne 5,17. E[hits] modèle 27,76 vs 27 observés (aligné). E[profit] +32,46 vs +20,36 réalisé.

C'est **cette** période qui produit le +8,3 % agrégé (+20,36 u vs net total +13,43 u ; part 152 % du net). Elle recouvre `calibration_select`. Ce n'est pas un hold-out du candidat Elo.

---

## 18. August–September / Final Test

53 matchs (weekend 17 + suivantes 36 ; PL 30, L1 23). 68 picks.

| Couche | n | Hits | Hit rate | Profit | ROI |
| --- | ---: | ---: | ---: | ---: | ---: |
| Elo argmax / Value settled | 53 | 23 | 43,4 % | −11,09 | −20,9 % |
| Naive HOME | 53 | 18 | 34,0 % | −11,51 | −21,7 % |
| **AI Picks** | **68** | **14** | **20,6 %** | **−6,93** | **−10,2 %** |

Wilson 95 % hit rate : **12,7 % – 31,6 %**.

Détail `final_test` :

| Sous-fenêtre | Matchs | Picks | Hits | Profit | ROI |
| --- | ---: | ---: | ---: | ---: | ---: |
| Weekend 21–24 août | 17 | 21 | 3 | −6,78 | −32,3 % |
| 28 août – 6 sept. | 36 | 47 | 11 | −0,15 | −0,3 % |
| **Total `final_test`** | **53** | **68** | **14** | **−6,93** | **−10,2 %** |

HDA : HOME 25, DRAW 20, AWAY 23. Cote moyenne 4,74 (similaire à mai). E[hits] 20,97 vs **14** observés. E[profit] +21,52 vs **−6,93**.

**Le +8,3 % global n'existe pas dans `final_test`.** Intervalles de hit rate mai et `final_test` se chevauchent : on ne peut pas affirmer statistiquement que les hit rates diffèrent. Les P&L, eux, sont de signes opposés et dominés par quelques longues cotes.

---

## 19. AI Picks vs Elo

| Relation pick vs argmax | n | Hits | Hit rate | Profit | ROI | Odds moy. |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Pick = argmax | 40 | 14 | 35,0 % | **−3,18** | −8,0 % | 2,82 |
| Pick ≠ argmax | 121 | 27 | 22,3 % | **+16,61** | +13,7 % | 5,71 |

Les 40 identiques = les 40 matchs dont l'argmax a EV ≥ 0 (79 argmax ont EV < 0). Différents : 54 DRAW + 47 AWAY + 20 HOME outsider.

Le P&L positif agrégé, **quand il existe (mai)**, vient de la mécanique Value (issues EV+ non-argmax), pas de « mieux suivre Elo ». Sur `final_test`, cette même mécanique ne suffit pas à un ROI positif.

Value settled (−13,1 %, 119 u) vs AI Picks (+8,3 %, 161 u) s'explique par :

1. filtre `EV ≥ 0` qui écarte les favoris à cote courte ;
2. multi-picks (49 matchs × 2 u) ;
3. exposition DRAW/AWAY à cotes 4–8 ;
4. **et** un mélange temporel où mai porte le net.

Ce n'est pas la même unité, ni le même pari.

---

## 20. Uncertainty

**Hit rate (Wilson 95 %, z = 1,96) :**

| Ensemble | n | Hits | Hit rate | Wilson 95 % |
| --- | ---: | ---: | ---: | --- |
| AI Picks agrégé | 161 | 41 | 25,5 % | 19,4 % – 32,7 % |
| Mai | 93 | 27 | 29,0 % | 20,8 % – 38,9 % |
| `final_test` | 68 | 14 | 20,6 % | 12,7 % – 31,6 % |
| Elo 119 | 119 | 54 | 45,4 % | 36,7 % – 54,3 % |

**ROI :** un intervalle paramétrique n'est pas adapté. Les picks d'un même match ne sont pas indépendants ; les profits sont lourds (un hit à 9,20 vaut 8,2 u). Un bootstrap i.i.d. (5000 tirages, graine 0) donne un intervalle empirique approximatif **−22 % – +40 %** autour du +8,3 % : il **surestime** la précision et est rapporté seulement pour montrer la largeur. **Pas une vérité fréquentiste.**

Conclusion d'incertitude : n = 161 reste petit pour un ROI de longues cotes. Le signe du P&L bascule si on retire 2 gagnants, ou si on se restreint à `final_test`.

---

## 21. Anomalies

| Contrôle | Résultat |
| --- | --- |
| Formules implied / no-vig / edge / EV | PASS |
| Ranking | PASS (161/161) |
| Hit rate / ROI / drawdown vs JSON | PASS |
| `available_at` ≤ `kickoff_at` / `cutoff_at` | PASS (119/119 et 161/161) |
| Snapshot après cutoff | 0 |
| Âge max | 6,16 h < 24 h ; `stale_odds=0` |
| Duplicate `(match_id, selection)` | 0 |
| HOME/AWAY flip | 0 sur les 119 |
| Match inventé | 0 |
| Paris isolé (club `4508`) | 6 exclus, 0 cote |
| Rennes/PSG | exclusion labellisée conservée |
| `negative_ev` 196 + 161 = 357 | PASS |
| `data_mode=live`, provider `the-odds-api-v4` | PASS |
| Versions modèle / Value / AI Picks | PASS |
| PIT / anti-leakage / parités / reproductibilité | PASS (JSON run) |

**Aucune anomalie moteur, PIT, identité ou de calcul identifiée.**

Le +8,3 % agrégé sans séparation temporelle, dans un rapport qui s'arrêterait là, serait une **présentation trompeuse**, pas un bug : mai et `final_test` ont des signes opposés.

---

## 22. Findings

1. **Le +8,3 % est concentré**, pas réparti. Hors top 2 gagnants, le ROI est négatif.
2. **Deux à cinq gagnants à cote 7–9** expliquent le net (Hull, Lille AWAY, Chelsea AWAY, PSG AWAY, City AWAY).
3. **Les cotes 5–10** apportent +11,81 u ; > 10 est 0/5 (−5 u). Hit rate 25,5 % compatible avec des cotes ~5.
4. **AWAY +17,10 u** ; HOME −5,21 u ; DRAW +1,54 u.
5. **PL +5,14 u / L1 +8,29 u** — les deux ligues positives en mai, négatives en `final_test`.
6. **Mai / `calibration_select` : ROI +21,9 %** (+20,36 u, 93 picks). Hits ≈ espérance modèle.
7. **Août–septembre / `final_test` : ROI −10,2 %** (−6,93 u, 68 picks). Hits 14 vs ~21 attendus.
8. **Le +8,3 % n'existe pas dans `final_test`.** Il est porté par `calibration_select`.
9. **AI Picks ≠ Elo.** Le P&L agrégé positif (lorsqu'on mélange les périodes) vient des 121 picks non-argmax et des 49 doubles, pas de l'argmax settlé (−13,1 %).
10. Le hit rate 25,5 % vs 45,4 % Elo est attendu si on prend des issues à P ~30 % et cotes ~5.
11. **Pas d'anomalie** de données ou de moteur.
12. Le signal n'est **pas** assez robuste pour conclure, ni pour tuner, ni pour promouvoir. Il l'est assez pour **ne pas corriger le moteur** et, si on continue, collecter **plus de `final_test`**, pas plus de mai.

---

## 23. Limitations

1. 119 matchs / 161 picks, deux mois calendaires effectifs, deux ligues, 1X2 seulement.
2. Mai ∈ `calibration_select` ; ce n'est pas un OOS du candidat.
3. `final_test` ici = 53 matchs / 68 picks — encore petit, et il inclut le weekend déjà analysé (ROI −32 %).
4. Last-complete bookmaker, pas Pinnacle préféré.
5. Leave-out des top gagnants est descriptif ; il ne définit pas un nouveau produit.
6. Labels parquet non recroisés avec un feed de scores externe dans cette branche.
7. Bootstrap ROI non i.i.d.
8. Rennes/PSG et Paris isolé restent hors scoring, par règle existante.

---

## 24. Recommendation

**E. Conserver la stratégie et collecter davantage de données** — opérationnellement **A. continuer l'expansion du dataset**, bornée, **surtout des fenêtres type `final_test`**, même cadence, mêmes seuils.

Justification :

- **B. Corriger une anomalie** — non. Aucune identifiée.
- **C. Revoir le modèle** — non comme suite immédiate. Elo 45,4 % / never-DRAW est un fait déjà connu ; ce n'est pas un bug de ce run.
- **D. Revoir la stratégie Value** — non sur la base de n = 161 ni pour « garder le +8,3 % ». Le filtre EV≥0 + multi-picks est le comportement 0.1 mesuré. Le changer ici serait du tuning.
- **E / A** — le moteur est propre ; l'échantillon `final_test` est trop petit et actuellement négatif ; un élargissement **sans retuning** est la seule voie qui ne confond pas mai avec une preuve.

Ne pas élargir pour « retrouver un ROI positif ». Ne pas ajouter de ligues ou de grilles 5 minutes pour lisser le P&L. Ne pas présenter 119 comme OOS.

---

## 25. Verdict

**NO ANOMALY FOUND**

| Question | Réponse |
| --- | --- |
| 1. +8,3 % réparti ou concentré ? | **Concentré.** Hors top 2, ROI < 0. |
| 2. Combien de gagnants expliquent le profit ? | Top 1 = 61 % du net ; top 2 inversent le signe. |
| 3. Longues cotes ? | 5–10 : +11,81 u du net +13,43. > 10 : 0/5. |
| 4. HOME/DRAW/AWAY ? | AWAY +17,10 u ; HOME −5,21 u. |
| 5. PL / L1 ? | Les deux positives en mai, négatives en `final_test`. |
| 6. Mai / `calibration_select` ? | **+21,9 %** (93 picks). Porte le global. |
| 7. Août–sept. / `final_test` ? | **−10,2 %** (68 picks). |
| 8. +8,3 % dans `final_test` ? | **Non.** |
| 9. AI Picks vs Elo ? | Univers différent. P&L agrégé + vient des non-argmax / doubles, surtout en mai. Elo settlé −13,1 % sur 119 matchs. |
| 10. Hit rate 25,5 % vs cotes élevées ? | Compatible (cote moy. 4,99, P moy. 30 %). |
| 11. Anomalie ? | **Non** (moteur, PIT, identité, calcul). |
| 12. Assez robuste pour un backtest beaucoup plus large ? | Assez pour **ne pas toucher au moteur**. Pas assez pour croire le +8,3 %. Un élargissement `final_test` borné est raisonnable ; ce n'est pas une validation de stratégie. |

`football-elo-v1-candidate` reste candidate. Value 0.1 et AI Picks 0.1 restent inchangés.

**Performance descriptive sur l'échantillon étudié ; insuffisante pour conclure à une rentabilité future.**
