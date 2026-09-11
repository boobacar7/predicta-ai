# Value Engine 0.1

## Périmètre

`value-engine-0.1` évalue uniquement le marché football 1X2. Il consomme les
probabilités calibrées du Prediction Service et les snapshots de l'Odds
Service. Il ne calcule, ne corrige et ne remplace aucune probabilité du modèle.

Le moteur fournit une analyse statistique. Il ne produit ni recommandation,
ni certitude sur un résultat, ni promesse de rendement.

L'implémentation serveur unique est `apps/api/app/value_engine/calculator.py`.
La version `value-engine-0.1` y est définie une seule fois. Les surfaces
catalogue (`GET /value`) et football (`GET /football/value/{match_id}`)
réutilisent ce calculateur. `overround` est la somme des probabilités
implicites, jamais `Σ 1/odds − 1`.

## Entrées obligatoires

Une évaluation exige :

- une prédiction football 1X2 valide pour le match demandé ;
- les probabilités `HOME`, `DRAW` et `AWAY`, chacune dans `(0, 1)`, dont la
  somme vaut `1` à la tolérance contractuelle ;
- les métadonnées `model_version`, `model_status`, `dataset_version`,
  `feature_schema_version` et `cutoff_at` ;
- un snapshot complet contenant exactement les trois sélections ;
- une cote décimale finie strictement supérieure à `1` par sélection ;
- une source, un `provider_id`, un bookmaker et un `data_mode` explicites ;
- des timestamps UTC cohérents et un snapshot respectant le cutoff.

Une entrée incomplète ou invalide provoque une erreur RFC 9457. Le moteur ne
retourne pas de résultat partiel.

## Formules

Pour une cote décimale `O` :

```text
implied_probability = 1 / O
```

Les calculs utilisent `Decimal`. Pour le marché complet :

```text
raw_i = 1 / odds_i
overround = sum(raw_i)
no_vig_i = raw_i / overround
```

La division décimale peut laisser un résidu d'arrondi de l'ordre de `10^-28`
avec la précision par défaut (28 chiffres). Le moteur refuse un résidu
strictement plus grand que `1e-18`, ce qui signale une vraie erreur
arithmétique. Le résidu restant, s'il existe, est alloué de façon
déterministe à la sélection `AWAY` (dernier élément de l'ordre canonique
`HOME`, `DRAW`, `AWAY`). Les trois probabilités no-vig retournées somment
alors exactement à `Decimal(1)` et restent dans `(0, 1)`.

Dans cette version, le champ `overround` désigne explicitement la somme des
probabilités implicites brutes, conformément au contrat HTTP. La marge au sens
`sum(raw_i) - 1` n'est pas exposée sous ce nom.

Pour une probabilité modèle `p` :

```text
edge = p - implied_probability
ev = (p * O) - 1
```

`edge` et `ev` sont des ratios bruts. Par exemple, `0.20` signifie `20 %`.
L'edge utilise la probabilité implicite brute ; la probabilité no-vig reste
exposée séparément et ne la remplace jamais silencieusement.

## Exemple déterministe

Entrées :

```text
prediction = HOME 0.60, DRAW 0.20, AWAY 0.20
odds       = HOME 2.00, DRAW 4.00, AWAY 5.00
```

Pour `HOME` :

```text
implied_probability = 1 / 2.00 = 0.50
edge = 0.60 - 0.50 = 0.10
ev = (0.60 * 2.00) - 1 = 0.20
```

## Point-in-time

La frontière PIT est inclusive :

```text
odds.available_at <= cutoff_at
```

`cutoff_at` est le cutoff de la requête. Si le Prediction Service retourne un
`prediction.cutoff_at` strictement postérieur au cutoff demandé, l'évaluation
est refusée. L'Odds Service n'utilise jamais `prediction.cutoff_at` pour
sélectionner une cote lorsque la requête fournit un cutoff.

Convention de timestamps du domaine :

```text
collected_at <= available_at <= cutoff_at
```

`collected_at` est le moment de collecte. `available_at` est le moment où la
donnée est utilisable. Une cote avec `available_at > cutoff_at` n'est jamais
utilisée, y compris lorsque `available_at` dépasse le cutoff d'une seule
microseconde.

L'Odds Service choisit le snapshot **complet** éligible le plus récent selon
`available_at`, puis `collected_at`, puis son identifiant stable. Un snapshot
incomplet plus récent ne masque pas un snapshot complet plus ancien. Si des
snapshots existent uniquement après le cutoff, l'évaluation est refusée
comme fuite temporelle.

Les timestamps RFC 3339 conservent les fractions de seconde. Un cutoff
sérialisé peut donc être rejoué à l'identique.

Les snapshots sont append-only. Un même identifiant interne ou un même couple
`(source, provider_id)` ne peut pas écraser une ancienne cote. Les historiques
sont isolés par `source` et `data_mode` du provider actif. Un fetch provider
en échec n'empêche pas le rejeu d'un historique déjà persisté pour ce
provider ; il ne synthétise aucune cote.

## Providers et data_mode

`OddsProvider` isole le domaine des fournisseurs externes.

- `MockOddsProvider` fournit uniquement des fixtures fictives, déterministes et
  marquées `data_mode=mock`.
- `LiveOddsProvider` est une frontière non configurée en V0.1. Il retourne une
  erreur explicite et ne synthétise jamais de cote live.

La source des cotes et le `data_mode` du provider doivent correspondre au
snapshot. Un mélange incohérent est refusé.

## Versioning et métadonnées

Chaque réponse contient :

- `value_engine_version = value-engine-0.1` ;
- `model_version`, `model_status`, `dataset_version` et
  `feature_schema_version` provenant du Prediction Service ;
- `odds_source` provenant du snapshot ;
- `cutoff_at`, `generated_at` et `data_mode`.

Le modèle reste `football-elo-v1-candidate` avec le statut `candidate`. Cette
intégration ne le promeut pas.

Toute modification sémantique des formules, de la convention d'overround ou de
la politique PIT exige une nouvelle version du moteur.

## API et erreurs

L'opération publique est :

```text
GET /api/v1/football/value/{match_id}?cutoff_at=<RFC3339>
```

Les succès utilisent l'enveloppe API v1 et répètent `request_id` dans le header
`X-Request-ID`. Les erreurs utilisent `application/problem+json` selon RFC 9457.

Types d'erreur propres au flux :

- `/problems/odds-unavailable` ;
- `/problems/incomplete-odds-market` ;
- `/problems/odds-temporal-leakage` ;
- `/problems/invalid-prediction`.

Les erreurs existantes du Prediction Service, notamment prédiction PIT absente,
artefact indisponible et fuite temporelle modèle, sont propagées sans être
transformées en données partielles.

## Limitations V0.1

- football 1X2 uniquement ;
- un seul snapshot/bookmaker est évalué à la fois ;
- aucun provider live réel n'est branché ;
- aucune agrégation multi-bookmaker, mouvement de cote ou politique de
  fraîcheur supplémentaire ;
- aucune création d'AI Picks et aucune recommandation frontend ;
- les limites existantes de provisioning du modèle candidate restent hors
  périmètre ;
- `available_at` appartient au snapshot complet, pas à chaque sélection.
  Un adapter live futur doit assembler un snapshot atomique ; un marché
  partiel est refusé jusqu'à complétude.

L'architecture Odds/Value n'ajoute aucune dépendance à un dataset ou artefact
local. Seul le Prediction Service conserve ses dépendances de provisioning
existantes.
