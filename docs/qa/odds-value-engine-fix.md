# Odds + Value Engine — Correctifs QA

## Périmètre

Correctifs ciblés des findings de
`docs/qa/odds-value-engine-validation.md` (commit QA `fa39654`, verdict
NO-GO). Aucun changement du modèle, du dataset, de l'artefact, du
Prediction Service interne, ni de provider live. Aucun AI Pick.

Branche : `agent/backend/fix-odds-value-engine`, à partir de
`agent/backend/odds-value-engine` (`2a2fb32`).

## Root causes

### B-01 — No-vig

`no_vig_probabilities()` exigeait `sum(no_vig) == Decimal(1)`. Les
divisions `raw_i / overround` laissent un résidu d'arrondi Decimal
(précision 28). Des marchés valides (`2/2/2`, `1.9/3.2/4.2`,
`2.1/3.3/3.7`) levaient `ArithmeticError` (~29,1581 % d'une grille
46 656).

### B-02 — Migration 0004

Le schéma 0003 autorise `odds_snapshots.data_mode=NULL`. La migration
0004 passait `data_mode` en `NOT NULL` sans backfill.

### H-01 / anti-leakage

Le Value Engine transmettait le cutoff demandé au Prediction Service,
puis sélectionnait les cotes avec `prediction.cutoff_at`. Un cutoff
retourné postérieur ouvrait une fenêtre post-requête.

### H-02 / H-03

`history()` filtrait seulement `match_id` et `market`. `market_at()`
appelait le provider avant toute lecture : une panne provider bloquait
un snapshot PIT déjà persisté.

### H-04 / OpenAPI

Le service prenait le dernier snapshot éligible, même incomplet. Le
contrat promet le dernier snapshot **complet**.

### H-05 / reproductibilité

`to_rfc3339` tronquait les microsecondes. Un cutoff `T+500 ms` sérialisé
devenait `T`, ce qui refusait au rejeu un snapshot accepté à `T+400 ms`.

### M-01 / M-02 / M-04 / M-06

Métadonnées Prediction manquantes → `AttributeError` ; course SQL
d'insertion convertie en `ValueError` ; pas de CHECK
`available_at >= collected_at` ni `data_mode ∈ {mock, live}` ; pas de
déduplication des sélections avant la contrainte unique.

## Corrections

- No-vig : tolérance `1e-18` sur le résidu, puis allocation déterministe
  du reliquat à `AWAY`. Le simplex retourné somme exactement à
  `Decimal(1)`. Un résidu plus grand reste une erreur arithmétique.
- Migration 0004 : `data_mode = COALESCE(data_mode, 'mock')` avant
  `NOT NULL` ; réparation `available_at >= collected_at` ; suppression
  des doublons de sélection ; CHECK constraints.
- Value Engine : refuse `prediction.cutoff_at > cutoff demandé` ;
  sélectionne les cotes avec le cutoff de la requête ; convertit les
  métadonnées manquantes en `InvalidPredictionError`.
- Odds Service : isole l'historique par `source` et `data_mode` ; un
  fetch en `OddsUnavailableError` n'empêche pas le rejeu ; choisit le
  dernier snapshot **complet** éligible.
- RFC 3339 : conservation des fractions de seconde.
- OpenAPI : description alignée sur le comportement réel.

Non corrigés volontairement :

- **H-06** : pas d'historique réel de cotes ; brancher un provider live
  est hors périmètre.
- **M-03** : `available_at` reste au niveau snapshot ; documenté.
- **M-05** : un seul `data_mode` exposé (celui des odds).

## Tests ajoutés

- marchés no-vig paramétrés + grille 46 656 ;
- odds invalides / manquantes / non numériques ;
- PIT `<`, `==`, `>` cutoff, y compris ±1 µs ;
- anti-leakage HOME/DRAW à T-10 min et AWAY à T+5 min, puis ACCEPT ;
- cutoff Prediction borné par la requête ;
- isolation source/`data_mode` ;
- rejeu malgré panne provider ;
- snapshot complet plus ancien vs incomplet plus récent ;
- rejeu RFC 3339 sub-seconde ;
- backfill `data_mode` dans 0004 ;
- métadonnées Prediction manquantes → erreur domaine ;
- consommation Prediction Service sans recalcul ;
- contrat OpenAPI « latest complete snapshot ».

## Quality gates

```text
ruff check app tests          PASS
mypy                          PASS, 55 fichiers
pytest                        107 passed, 0 failed, 0 xfailed
openapi-typescript            PASS
```

Les 60 tests préexistants du backend, plus la suite QA, restent verts.
Le modèle servi reste `football-elo-v1-candidate`.
