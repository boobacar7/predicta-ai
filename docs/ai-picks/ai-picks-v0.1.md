# AI Picks Engine V0.1

## Objectif

`ai-picks-0.1` transforme les analyses déjà validées du Prediction Service,
de l'Odds Service et de `value-engine-0.1` en opportunités statistiques
filtrées et classées. Il ne recalcule jamais les probabilités du modèle,
n'utilise ni LLM ni hasard, et ne constitue pas une recommandation de pari.

Le modèle servi reste `football-elo-v1-candidate`, avec
`model_status=candidate`. Il n'est ni champion ni production.

## Architecture

```text
Prediction Service
  → Odds Service (snapshot PIT immuable)
  → Value Engine
  → AI Picks eligibility
  → score et ranking déterministes
  → GET /api/v1/football/ai-picks
```

Le router construit uniquement la requête typée. Toute la logique se trouve
dans `apps/api/app/ai_picks/`.

## Univers V0.1

L'univers de matchs est explicite et configurable par
`PREDICTA_API_AI_PICKS_CANDIDATE_MATCH_IDS`. Les identités, ligues et kickoffs
sont résolus depuis le parquet PIT réel. La valeur par défaut contient le match
couvert par le provider de cotes fictif V0.1. Cette limite évite de parcourir
des milliers de matchs sans cotes et ne simule aucun provider live.

## Éligibilité et exclusions

Une sélection est éligible seulement si :

- la prédiction football 1X2 existe et ses probabilités somment à 1 ;
- `model_status`, les versions et le cutoff sont présents ;
- le marché HOME/DRAW/AWAY est complet et ses cotes sont valides ;
- le snapshot était disponible au cutoff canonique ;
- le résultat Value Engine correspond exactement aux formules versionnées ;
- l'âge des cotes et les trois seuils configurés sont respectés.

Une erreur n'est jamais ignorée. Elle produit une exclusion structurée :
`negative_ev`, `negative_edge`, `below_minimum_ev`,
`below_minimum_edge`, `below_minimum_model_probability`, `invalid_odds`,
`incomplete_market`, `prediction_unavailable`, `pit_unavailable`,
`invalid_prediction`, `invalid_value` ou `stale_odds`.

`candidate_model` est une information, pas une exclusion automatique.
Chaque pick conserve `model_status=candidate`.

## Score V0.1

La formule unique est :

```text
opportunity_score = EV + Edge
```

Elle est simple, audit-able et versionnée par `ai-picks-0.1`. La confiance
modèle n'est pas exposée par le Prediction Service V1 ; elle n'est donc pas
inventée et n'entre pas dans le score. La probabilité modèle ne doit pas être
interprétée comme une confiance distincte.

## Ranking

Tri total, stable et sans hasard :

1. `opportunity_score` décroissant ;
2. `EV` décroissant ;
3. `Edge` décroissant ;
4. fraîcheur des données décroissante ;
5. `match_id` croissant ;
6. sélection croissante comme dernier ordre total pour deux sélections du même match.

Les rangs sont calculés avant pagination et restent donc globaux.

## Seuils

Source centrale : `AiPicksThresholds`.

- `minimum_edge` : `0` par défaut ;
- `minimum_ev` : `0` par défaut ;
- `minimum_model_probability` : `0` par défaut, donc non contraignant en V0.1 ;
- `maximum_odds_age` : 24 heures par défaut.

`min_edge` et `min_ev` peuvent être relevés par requête. Les autres seuils
restent des paramètres d'exploitation afin de garder l'API V0.1 minimale.

## PIT et déduplication

Le moteur transmet le kickoff du candidat comme cutoff canonique au Value
Engine. Il refuse tout cutoff divergent et tout `available_at` postérieur.
Il ne recalcule jamais un cutoff.

La déduplication est héritée de l'Odds Service : pour
`match/market/source/data_mode`, il choisit le dernier snapshot complet dont
`available_at <= cutoff_at`; un snapshot incomplet plus récent ne masque pas
un snapshot complet éligible. AI Picks produit ensuite au plus une ligne par
`match/market/selection`.

## Data mode

Le `data_mode` vient du snapshot de cotes utilisé par le Value Engine. Une cote
du `MockOddsProvider` reste `mock` dans le pick et dans l'enveloppe. Aucun nom
de bookmaker réel n'est inventé. Aucun provider live n'est branché en V0.1.

## API et exemple

```http
GET /api/v1/football/ai-picks?date=2026-07-07&limit=20&min_edge=0.02&min_ev=0.03
```

Un item expose séparément l'identité du match, la probabilité modèle, la cote,
les probabilités implied/no-vig, les résultats Value Engine, le score/rang et
les métadonnées de version et PIT.

Pour `P(HOME)=0.60` et `odds=2.00` :

```text
implied_probability = 1 / 2.00 = 0.50
edge = 0.60 - 0.50 = 0.10
EV = 0.60 × 2.00 - 1 = 0.20
opportunity_score = 0.20 + 0.10 = 0.30
```

Ces nombres sont des mesures statistiques. Ils ne garantissent ni résultat ni
retour financier.

## Limitations acceptées

- H-06 : aucun historique de cotes réel ;
- M-03 : `available_at` au niveau snapshot ;
- M-05 : un seul `data_mode` exposé par source active ;
- univers de matchs explicitement configuré ;
- absence de signal de confiance distinct en V0.1 ;
- modèle Elo toujours candidate.
