# Odds + Value Engine — QA Validation

## Scope

Audit indépendant de la chaîne :

```text
Prediction API
  -> Odds Provider / Repository / Service
  -> sélection PIT du snapshot
  -> implied probability / overround / no-vig
  -> edge / EV
  -> GET /api/v1/football/value/{match_id}
```

Baseline auditée :

- branche source : `agent/backend/odds-value-engine` ;
- commit source : `2a2fb32` ;
- modèle consommé : `football-elo-v1-candidate` ;
- Value Engine : `value-engine-0.1`.

Exclusions respectées : aucun changement du modèle, dataset, artefact,
Prediction Service, frontend ou provider live. Aucun AI Pick n'a été créé.

## Environment

- macOS Darwin 25.6.0 ;
- Python 3.14.4 ;
- pytest 9.1.1 ;
- OpenAPI 3.1 ;
- repository mock pour les scénarios HTTP contrôlés ;
- PostgreSQL local inspecté en lecture seule : `odds_snapshots=0`.

Le dataset PIT et l'artefact locaux existants ont uniquement été consommés par
les tests Prediction Service déjà validés. L'architecture Odds/Value n'ajoute
pas de dépendance locale supplémentaire.

## Architecture reviewed

La séparation est conforme :

- `app/odds/providers.py` définit la frontière `OddsProvider` et sépare mock/live ;
- `app/odds/repository.py` et `app/odds/sql_repository.py` portent la persistance ;
- `app/odds/service.py` collecte, persiste et sélectionne le snapshot PIT ;
- `app/predictions/` demeure la seule source des probabilités modèle ;
- `app/value_engine/service.py` orchestre Prediction Service + Odds Service ;
- `app/value_engine/calculator.py` contient uniquement les formules déterministes ;
- le router appelle le service et construit l'enveloppe sans logique métier.

Le Value Engine ne produit aucune probabilité modèle. Il valide puis consomme
les trois probabilités retournées par le Prediction Service.

## Odds validation

Résultats :

- snapshots dataclasses immuables ;
- identifiants internes et `provider_id` obligatoires ;
- `source`, `bookmaker`, `match_id`, `market` et `data_mode` obligatoires ;
- cotes finies et strictement supérieures à `1` ;
- sélection unique dans un snapshot ;
- historique append-only, ordonné par `available_at`, `collected_at`, puis `id` ;
- réinsertion idempotente d'un snapshot identique ;
- conflit explicite si un identifiant ou `(source, provider_id)` tente de
  remplacer un snapshot différent ;
- plusieurs snapshots pour un match conservés et le dernier éligible choisi.

Le chemin mémoire a été testé en concurrence logique et en rejeu. Le chemin SQL
respecte les contraintes d'unicité, mais sa course d'insertion concurrente,
l'ordre de round-trip et les invariants DB restent couverts par des findings
MEDIUM.

L'historique du repository est actuellement filtré uniquement par `match_id` et
`market`. Il n'est pas isolé par source/provider ou `data_mode` : un service
configuré live peut sélectionner un snapshot mock déjà persisté. Ce défaut est
classé HIGH.

## PIT validation

Convention confirmée et conforme à la documentation :

```text
snapshot.available_at <= prediction.cutoff_at
```

La frontière est inclusive :

- `available_at < cutoff_at` : accepté ;
- `available_at == cutoff_at` : accepté ;
- `available_at > cutoff_at` : refusé.

Convention de timestamps du domaine :

```text
collected_at <= available_at
```

`collected_at` représente la collecte et `available_at` le moment où la donnée
est utilisable par le système. Cette relation implique qu'un snapshot éligible
par `available_at` ne peut pas avoir été collecté après le cutoff.

Un scénario mixte HOME/DRAW avant cutoff et AWAY après cutoff est refusé : le
snapshot pré-cutoff reste incomplet. Un snapshot complet dont les trois
sélections sont disponibles avant cutoff est accepté.

Deux défauts PIT complémentaires ont été reproduits :

- le Value Engine ne vérifie pas que `prediction.cutoff_at` est inférieur ou
  égal au cutoff demandé ; une implémentation Prediction défectueuse peut donc
  faire sélectionner une cote postérieure au cutoff de la requête ;
- le timestamp RFC3339 exposé tronque les microsecondes, ce qui peut rendre un
  rejeu du cutoff sérialisé différent de l'évaluation initiale.

## Implied probability

Formule vérifiée avec `Decimal` :

```text
implied_probability = 1 / decimal_odds
```

Cas indépendants :

- `2.00 -> 0.50` ;
- `4.00 -> 0.25` ;
- `5.00 -> 0.20`.

`None`, valeurs non numériques, négatives, nulles et inférieures ou égales à
`1` sont refusées.

## Overround / No-Vig

La documentation et l'implémentation utilisent la même convention :

```text
raw_i = 1 / odds_i
overround = sum(raw_i)
no_vig_i = raw_i / overround
```

Le cas `2.00 / 4.00 / 5.00` passe :

- raw : `0.50 / 0.25 / 0.20` ;
- overround : `0.95` ;
- somme no-vig : `1`.

Un défaut bloquant est toutefois présent. Le calcul exige ensuite :

```text
sum(no_vig) == Decimal(1)
```

Cette égalité stricte échoue dès que les divisions décimales nécessitent un
arrondi de contexte. Exemples valides refusés :

- `2.00 / 2.00 / 2.00` ;
- `1.90 / 3.20 / 4.20` ;
- `2.10 / 3.30 / 3.70`.

Probe exhaustif déterministe sur `46 656` marchés valides, avec chaque cote
comprise entre `1.5` et `5.0` par pas de `0.1` :

- marchés acceptés : `33 052` ;
- marchés rejetés par `ArithmeticError` : `13 604` ;
- taux d'échec : `29.1581 %`.

Le cas HTTP `1.90 / 3.20 / 4.20` retourne `500` au lieu d'une analyse value.
Le contrôle doit utiliser une tolérance numérique documentée ou allouer le
résidu d'arrondi de manière déterministe.

## Edge

Formule conforme :

```text
edge = model_probability - implied_probability
```

Vérifications :

- positif : `0.60 - 0.50 = 0.10` ;
- nul : `0.50 - 0.50 = 0` ;
- négatif : `0.40 - 0.50 = -0.10`.

Aucun seuil ni clamp positif n'est appliqué. L'implied brute et le no-vig
restent distincts.

## EV

Formule conforme :

```text
ev = model_probability * decimal_odds - 1
```

Vérifications :

- positif : `0.60 * 2.00 - 1 = 0.20` ;
- nul : `0.50 * 2.00 - 1 = 0` ;
- négatif : `0.40 * 2.00 - 1 = -0.20` ;
- hausse de la cote à probabilité constante : EV augmente ;
- hausse de la probabilité à cote constante : EV augmente ;
- cote inverse de la probabilité : EV nul.

EV est retourné comme ratio brut, jamais comme pourcentage formaté. Aucun clamp
positif n'est appliqué.

## Prediction integration

Le chemin nominal conserve :

- `model_version=football-elo-v1-candidate` ;
- `model_status=candidate` ;
- `dataset_version=football-1x2-history-0.3` ;
- `feature_schema_version=football-1x2-features-0.3`.

Les probabilités hors intervalle et les simplexes dont la somme diffère de `1`
sont refusés par `InvalidPredictionError`.

Une prédiction sans métadonnées obligatoires, construite pour simuler une
frontière interne corrompue, provoque actuellement `AttributeError` au lieu
d'un `InvalidPredictionError`. Le Prediction Service typé empêche normalement
ce payload, mais la défense en profondeur du Value Engine est incomplète.

## End-to-end validation

Scénario HTTP contrôlé :

```text
prediction = HOME 0.60, DRAW 0.20, AWAY 0.20
odds = HOME 2.00, DRAW 4.00, AWAY 5.00
```

Résultat :

- implied HOME : `0.50` ;
- edge HOME : `0.10` ;
- EV HOME : `0.20` ;
- overround : `0.95` ;
- somme no-vig : `1` ;
- candidate et `data_mode=mock` conservés ;
- `request_id` identique dans header et payload.

Trois `match_id` historiques présents dans le dataset Prediction Service ont
également traversé Prediction Service -> Odds Service -> Value Engine -> HTTP.
Les cotes de ces tests sont des fixtures QA explicitement mock, disponibles
dix minutes avant le cutoff. Aucun résultat historique n'a été inventé.

Le rejeu depuis un repository persisté reste couplé à un fetch provider exécuté
en premier. Une panne provider empêche donc l'utilisation d'un snapshot
historique pourtant disponible. Le provider live V0.1 non configuré bloque
ainsi tout replay SQL via le service public.

## Temporal leakage

Tests anti-leakage :

- dernier snapshot pré-cutoff sélectionné même si un snapshot futur existe ;
- snapshot disponible exactement au cutoff accepté ;
- snapshot uniquement post-cutoff refusé avec conflit temporel ;
- marché pré-cutoff partiel + sélection post-cutoff refusé ;
- `available_at` naïf ou antérieur à `collected_at` refusé ;
- vérification HTTP et service.

Avec le Prediction Service validé, aucune cote post-cutoff n'a été utilisée.
Avec une implémentation injectée retournant un cutoff ultérieur au cutoff
demandé, une cote située entre les deux cutoffs est acceptée. La frontière du
Value Engine ne défend donc pas seule la garantie anti-leakage.

La représentation V0.1 horodate le snapshot complet et non chaque sélection.
Un provider qui publie les sélections séparément doit donc assembler un
snapshot complet atomique ou conserver des snapshots partiels qui seront
refusés jusqu'à complétude.

## Error handling

Les erreurs principales respectent RFC 9457 :

- `status`, `type`, `title`, `detail`, `instance` nullable et `request_id` ;
- `application/problem+json` ;
- `X-Request-ID` identique au body ;
- marché incomplet : `422 /problems/incomplete-odds-market` ;
- odds absentes : `422 /problems/odds-unavailable` ;
- odds uniquement futures : `409 /problems/odds-temporal-leakage` ;
- prediction PIT absente : `422 /problems/pit-features-unavailable` ;
- prediction invalide : `422 /problems/invalid-prediction`.

Le défaut no-vig génère bien une enveloppe RFC 9457 générique, mais avec un
`500 /problems/internal` pour un marché valide. La structure RFC est correcte ;
le comportement fonctionnel ne l'est pas.

## OpenAPI

`contracts/openapi.yaml` correspond à l'endpoint réel :

- `GET /api/v1/football/value/{match_id}` ;
- paramètres `match_id`, `cutoff_at` et `X-Request-ID` ;
- schémas fermés pour prediction, odds, market probabilities, value et metadata ;
- enums candidate/champion et mock/live ;
- champs de version et provenance requis ;
- réponses `409`, `422`, `503` et défaut Problem Details.

Les tests jsonschema passent et `openapi-typescript 7.13.0` génère le client
sans erreur.

Une divergence sémantique existe néanmoins : le contrat promet le « latest
complete odds snapshot », alors que le service choisit d'abord le dernier
snapshot éligible et le refuse s'il est incomplet, même lorsqu'un snapshot
complet plus ancien existe. OpenAPI est donc syntaxiquement valide mais n'est
pas conforme au comportement sur ce cas.

Le contrat ne contient pas encore d'exemples complets pour les succès et
erreurs Value ; ceci est classé LOW.

## Regression tests

Commandes exécutées :

```text
ruff check app tests
mypy
pytest -rxX
npx --yes openapi-typescript contracts/openapi.yaml
```

Résultats :

- Ruff : PASS ;
- mypy strict : PASS, `55` fichiers source ;
- pytest : `85` cas collectés, `74 passed`, `11 xfailed`, aucune régression ;
- les onze xfails documentent les défauts numériques, migration, PIT,
  historique/provider, contrat et validation Prediction ;
- OpenAPI TypeScript : PASS.

Les `60` tests précédemment présents continuent de passer.

## Findings

### BLOCKER

**B-01 — No-vig refuse une proportion importante de marchés valides**

`calculator.no_vig_probabilities()` compare une somme Decimal arrondie à
`Decimal(1)` par égalité stricte. Le probe QA échoue sur `13 604 / 46 656`
marchés valides (`29.1581 %`) et un marché ordinaire retourne HTTP 500.

Impact : Value Finder et AI Picks auraient une couverture imprévisible et des
erreurs serveur sur des cotes valides. Correction obligatoire avant démarrage.

**B-02 — Migration 0004 non sûre pour un état 0003 valide**

Le schéma antérieur autorise `odds_snapshots.data_mode=NULL`. La migration
backfill `provider_id`, timestamps et source, puis applique `data_mode NOT
NULL` sans backfill ni préflight. Une base 0003 contenant une cote legacy sans
mode échoue au déploiement. La base locale inspectée est vide, ce qui masque le
défaut dans le happy path actuel.

### HIGH

**H-01 — Cutoff retourné par Prediction Service non borné par la requête**

Le cutoff demandé est transmis au Prediction Service, mais le Value Engine
utilise ensuite sans vérification `prediction.cutoff_at`. Une cote entre le
cutoff demandé et un cutoff retourné ultérieur est acceptée.

**H-02 — Historique non isolé par source/provider et data_mode**

Les snapshots nouvellement fetchés sont validés contre le provider actif, mais
la requête d'historique filtre uniquement `match_id` et `market`. Un snapshot
mock ou d'une autre source peut être sélectionné dans un chemin live.

**H-03 — Une panne provider empêche le rejeu de l'historique persisté**

`OddsService.market_at()` fetch le provider avant de lire le repository. Une
erreur provider interrompt la requête même lorsqu'un snapshot PIT éligible est
déjà persisté. Le `LiveOddsProvider` non configuré rend notamment le replay SQL
inaccessible via ce chemin.

**H-04 — Snapshot incomplet récent masque un snapshot complet**

Le service choisit le dernier snapshot éligible avant de vérifier sa
complétude. Un snapshot complet plus ancien n'est pas sélectionné si le plus
récent est partiel, contrairement à la description OpenAPI « latest complete
odds snapshot ».

**H-05 — Sérialisation sub-seconde non rejouable**

Les microsecondes sont supprimées par `to_rfc3339`. Un snapshot disponible à
`T+400 ms`, accepté avec cutoff `T+500 ms`, est exposé avec cutoff `T`; rejouer
ce cutoff sérialisé refuse ensuite le même snapshot.

**H-06 — Validation historique limitée à des cotes mock**

La base inspectée contient zéro snapshot de cote et le provider mock produit un
seul match par défaut. Trois matchs historiques réels ont été testés avec des
cotes QA mock clairement identifiées, ce qui valide le code PIT mais pas la
provenance d'un historique réel de cotes.

Impact : aucune conclusion empirique n'est possible sur la qualité temporelle
d'un futur flux provider ou d'un historique réel. Ce finding n'autorise pas à
inventer ou brancher des cotes live dans cette tâche.

### MEDIUM

**M-01 — Métadonnées Prediction manquantes non converties en erreur domaine**

Une sortie interne incomplète du Prediction Service atteint un
`AttributeError`, puis un `500`, au lieu de `/problems/invalid-prediction`.

**M-02 — Course SQL d'insertion non idempotente**

Deux insertions concurrentes du même snapshot peuvent toutes deux manquer le
`session.get()`. La seconde contrainte SQL est convertie en `ValueError`, non en
relecture idempotente ou erreur RFC métier.

**M-03 — Atomicité des timestamps de sélection implicite**

`available_at` appartient au snapshot, pas à chaque sélection. Cette convention
est sûre par refus des snapshots partiels, mais doit être imposée au futur
adapter live pour empêcher l'assemblage de sélections issues de cutoffs
différents.

**M-04 — Invariants et round-trip SQL incomplets**

La base n'impose pas `available_at >= collected_at`, les valeurs autorisées de
`data_mode`, ni l'ordre des sélections. L'égalité idempotente du dataclass est
pourtant sensible à l'ordre. `observed_at` est en outre remplacé par
`collected_at`, ce qui perd une dimension de provenance provider.

**M-05 — Provenance mixte Prediction/Odds non distinguée**

La réponse expose un seul `data_mode`, celui des odds. Une prediction issue de
features live combinée à des odds mock est globalement marquée mock, sans modes
séparés pour les deux entrées.

**M-06 — Migration sans préflight des doublons de sélection**

Le schéma précédent autorisait plusieurs lignes identiques
`(snapshot_id, selection)`. La nouvelle contrainte unique échoue si de tels
doublons existent ; aucune détection préalable ni procédure de remédiation
n'est documentée.

### LOW

- OpenAPI n'expose pas d'exemple complet succès/erreur pour le nouvel endpoint.
- `Settings.value_formula_version` n'est pas utilisé par le nouveau moteur.
- Les concepts DB `provider` et `source` reçoivent la même valeur.
- Deux implémentations nommées `value-engine-0.1` utilisent des conventions
  différentes d'overround : la nouvelle retourne la somme brute, l'ancienne
  couche frontend retourne la marge et la borne à zéro.
- Les warnings Starlette sur HTTP 422 et TestClient sont non bloquants.

### INFO

- Le modèle reste candidate ; aucune promotion implicite détectée.
- `data_mode=mock` est explicite et le provider live non configuré refuse sans
  synthétiser de cote.
- Aucun cache ou fallback silencieux n'intervient dans ce chemin.
- Les deux limitations locales connues du Prediction Service restent hors
  périmètre et ne sont pas aggravées.

## Final Verdict

**NO-GO**

Résumé :

- ODDS SNAPSHOTS : PASS
- PIT ODDS : FAIL
- IMPLIED PROBABILITY : PASS
- NO-VIG : FAIL
- EDGE : PASS
- EV : PASS
- MARKET COMPLETENESS : PASS
- PREDICTION INTEGRATION : FAIL
- ANTI-LEAKAGE : FAIL
- REPRODUCIBILITY : FAIL
- RFC9457 : PASS
- OPENAPI : FAIL
- REGRESSION : PASS

Comptage :

- BLOCKERS : 2
- HIGH : 6
- MEDIUM : 6

Il ne faut pas commencer AI Picks + Value Finder tant que les blockers ne sont
pas corrigés et que les risques HIGH PIT, isolation et rejeu ne sont pas
arbitrés/corrigés. La décision devra ensuite être rejouée sur la suite QA,
notamment les cas actuellement marqués xfail.
