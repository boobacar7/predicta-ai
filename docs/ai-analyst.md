# AI Analyst football V0.1

## Objectif

`ai-analyst-0.1` explique un match football 1X2 à partir d'un contexte déjà
validé. Il ne choisit pas de pari, ne recalcule pas les probabilités, ne
réimplémente pas le Value Engine et n'invente aucune donnée factuelle.

Le modèle servi reste `football-elo-v1-candidate` avec
`model_status=candidate`. Il n'est ni promu ni présenté comme un champion.

## Architecture

```text
validated identity
  → Prediction Service
  → Value Engine (optionnel)
  → AnalystContext immuable
  → AnalystEvidence (faits whitelistés, typed)
  → LLM JSON { narrative, claims[] }
  → GroundedNarrative / GroundedClaim[]
  → ClaimValidator (valeurs vs AnalystContext)
  → EvidenceValidator (evidence_id + evidence.type)
  → assert_grounded
  → render (templates backend)
  → GET /api/v1/football/ai-analyst/{match_id}
```

Le LLM n'est pas autorisé à déclarer qu'une phrase est grounded. Il fournit
une narration stylistique et des claims structurées. Le backend compare
chaque claim à `AnalystContext` / `AnalystEvidence`, puis rend le texte
factuel. La prose n'est jamais une source de vérité.

Exemple : `probability_comparison` / AWAY > HOME est calculé contre
`P(AWAY)` et `P(HOME)`. Si HOME = 41,7 % et AWAY = 29,2 %, la claim est
fausse : la narration LLM entière est rejetée. « AWAY is more likely than
HOME » dans le texte n'est pas analysé comme preuve.

Une evidence `type=odds` ou `implied_probability` ne peut pas valider une
claim `model_probability`. `GroundedClaim` / `GroundedNarrative` restent
internes : le DTO HTTP ne change pas.

`DeterministicAnalystProvider` reste le narrator par défaut
(`PREDICTA_API_ANALYST_NARRATOR=deterministic`) et ne nécessite aucune clé
externe. `LLMAnalystProvider` est un narrator optionnel derrière le même
port `AnalystProvider`. Il ne devient jamais source of truth.

## Contrat

```text
GET /api/v1/football/ai-analyst/{match_id}?cutoff_at=<RFC3339>
```

La réponse enveloppe standard porte `data_mode`, `generated_at` et
`request_id`. `data` contient :

- identité : `match_id`, `home_team`, `away_team`, `league`, `kickoff_at` ;
- `model_favorite` : issue de plus haute probabilité modèle ;
- `prediction` : probabilités 1X2, versions, statut, cutoff ;
- `value` : métriques de l'issue expliquée, plus `value_selection` ;
- `analyst` : résumé, facteurs, forces, risques, confiance, qualité,
  `analysis_version=ai-analyst-0.1`.

`home_team` et `away_team` sont requis mais nullables. Un nom absent n'est
jamais remplacé.

## Model favorite et value selection

Deux concepts distincts :

- `model_favorite` : issue à plus haute probabilité modèle, tie-break
  `HOME`, `DRAW`, `AWAY`. C'est l'issue expliquée.
- `value.selection` : même issue. Les champs `odds`, `implied_probability`,
  `edge` et `ev` portent **uniquement** sur ce favori modèle.
- `value.value_selection` : issue au plus haut EV théorique du résultat
  Value Engine, même tie-break. Informationnelle seulement.

Ces champs ne sont ni un pick, ni un pari, ni une recommandation. Un EV
positif sur `value_selection` n'autorise aucun langage de mise.

`model_favorite` et `value_selection` ne sont pas interchangeables :

- « AWAY is the model favorite » est faux si le favori modèle est HOME ;
- « HOME is the best value » est faux si `value_selection` est AWAY ;
- l'EV / l'edge du contexte portent sur `value.selection` (le favori
  modèle), jamais sur `value_selection`. Attribuer l'EV HOME à AWAY est
  rejeté même si les deux issues sont citées.

Le Value Engine n'est pas modifié. L'analyste n'est pas un moteur de picks.

## Provenance

Chaque facteur porte un `source` interne :

- `football-prediction-service`
- `value-engine-0.1`
- identifiant du snapshot de cotes lorsqu'un âge de cote est exposé

Le résumé n'insère que des nombres présents dans le contexte. S'il n'y a pas
de cote, le texte dit que l'implicite, l'edge et l'EV sont absents. Un
pourcentage, une cote, un EV ou une équipe absents du contexte font échouer
`assert_grounded`, y compris lorsqu'ils n'apparaissent que dans le texte.

## PIT

Le cutoff demandé est transmis tel quel au Prediction Service puis, en cas de
succès, au Value Engine. Les règles déjà validées s'appliquent :

- `cutoff_at > kickoff` → `/problems/temporal-leakage` (409)
- `cutoff_at < kickoff` → `/problems/pit-features-unavailable` (422)
- snapshot de cotes avec `available_at > cutoff_at` →
  `/problems/odds-temporal-leakage` (409)
- aucune cote → section value `unavailable`, pas une cote inventée

Le service refuse aussi un contexte dont `kickoff_at != prediction.cutoff_at`
ou dont `odds.available_at > cutoff_at`. Aucune donnée postérieure au cutoff
n'entre dans `AnalystContext`.

## Confiance

Aucun score numérique arbitraire n'est calculé. `confidence.level` est
qualitatif et déterministe :

1. `high` seulement si modèle champion, `data_mode=live`, identité complète
   et value disponible ;
2. `medium` si modèle candidat, identité complète et value disponible,
   y compris lorsque `data_mode=mock` ;
3. `low` si l'identité est incomplète, si la value est absente, ou s'il
   existe une autre lacune de métadonnées.

Un modèle `candidate` n'émet jamais `high`, quelle que soit la magnitude
des probabilités. Cette règle, le champ `confidence.rule`, OpenAPI et le
comportement HTTP sont identiques.

## Provider déterministe

`DeterministicAnalystProvider.generate_analysis(context)` est une fonction
pure : pas d'horloge, pas d'I/O, pas d'aléa. Deux appels sur le même
contexte produisent le même objet. `generated_at` est copié du contexte,
lui-même fixé par l'horloge injectable du service.

## AnalystContext et AnalystEvidence

`AnalystContext` est la whitelist immuable passée au provider : identité
structurelle, probabilités, métadonnées modèle, value optionnelle,
`generated_at`, `data_mode`.

`context.evidence()` expose ces faits comme `AnalystEvidence` :

- `evidence_id`, `category`, `source_field`, `value`
- `source` / provenance
- `availability`
- `cutoff_at` lorsqu'il s'applique

Chaque `AnalystEvidence` a un `evidence_type` dérivé du champ source
(`model_probability`, `odds`, `ev`, `identity`, `data_mode`, …).

Quatre couches restent séparées :

1. **faits** issus du contexte (`AnalystContext` → `AnalystEvidence`) :
   identité, probabilités, cotes, edge, EV, versions, cutoff, `data_mode` ;
2. **evidence** : whitelist immuable. Un `evidence_id` inconnu, une
   evidence indisponible, ou un `evidence.type` incompatible avec
   `claim_type` est refusé ;
3. **claims** : `GroundedClaim` porte `claim_type`, `subject`,
   `value` / `compare_to` / `relation`, et `evidence_ids`.
   `ClaimValidator` compare la structure aux valeurs du contexte.
   HOME, AWAY et DRAW sont résolus vers les équipes du contexte ; une
   équipe absente est rejetée. Les faits sportifs (`injury`, `lineup`,
   `result`, `ranking`, `event`, `statistic`) n'ont pas d'evidence V0.1
   et sont toujours rejetés ;
4. **narration** : le champ `narrative` du LLM est stylistique seulement
   (pas de chiffres, pas de labels HOME/AWAY/DRAW, pas de noms d'équipes).
   Les phrases factuelles publiées sont rendues par le backend à partir
   des claims validées. Une prose qualitative sans fait nouveau reste
   autorisée si elle ne contredit pas le canal claims.

`DeterministicAnalystProvider` émet encore des `GroundedStatement` internes
puis `render_statements`. `LLMAnalystProvider` n'extrait plus de faits
depuis la prose : il exige des claims structurées.

Les DTOs `prediction` et `value` sont reconstruits par le service depuis
`AnalystContext`, jamais depuis le texte du provider.

## Provider LLM (narrator)

`AnalystProvider` est le port. `LLMAnalystProvider.generate_analysis(context)`
reçoit uniquement le contexte validé. **LLM output ≠ source of truth.**

Flux :

```text
AnalystContext
  → AnalystEvidence
  → LLMAnalystProvider (contexte sérialisé whitelisté uniquement)
  → StructuredNarrative { narrative, claims[] }
  → GroundedClaim[]
  → ClaimValidator
  → EvidenceValidator
  → assert_grounded
  → render
  → Analyst DTO
```

Toute erreur du chemin narrator (JSON malformé, schema, evidence inconnue,
claim non supportée, grounding, `RuntimeError`, timeout, erreur client)
retombe sur `DeterministicAnalystProvider` avec un DTO complet et
`provider=deterministic-v0.1`. Aucune narration LLM partiellement validée
n'est publiée. Les erreurs Prediction Service / Value Engine / PIT /
`ApiError` ne sont pas masquées. Un nom d'équipe qui contient un terme
interdit (`Injured FC`) est masqué avant le scan topic : l'exception reste
dans la boundary narrator.

Le LLM n'a pas le droit de définir `probabilities`, `odds`, `edge`, `EV`,
`model_version`, `dataset_version`, `cutoff_at` ou `data_mode`.

Le client livré est `mock-explainer-0.1` : un narrator déterministe qui
parle le schéma LLM, sans vendor externe ni secret. Aucune dépendance LLM
n'est ajoutée. Le frontend continue d'appeler
`GET /api/v1/football/ai-analyst/{match_id}` ; le backend reste la seule
boundary.

Le LLM ne peut jamais modifier :

- probabilités
- cotes
- edge / EV
- `model_version`
- `dataset_version`
- `value_engine_version`
- `cutoff_at`
- `data_mode`
- le résultat Value Engine
- `HistoricalMatchIdentity`
- le cutoff PIT

Le service reconstruit `prediction` et `value` depuis le contexte, puis
appelle `assert_grounded`. Un facteur, une `FactualClaim` ou un texte hors
evidence est refusé. Exemple : contexte HOME 41,7 % et résumé « HOME 80 % »
→ rejet, puis fallback déterministe. De même : claim HOME > 0,5 alors que
HOME = 41,7 % ; claim `model_favorite=AWAY` alors que le favori est HOME ;
claim EV « high » alors que EV HOME = −16,7 %.

## Sécurité anti-hallucination

Interdit :

- inventer cote, probabilité, blessure, composition, statistique, résultat,
  événement ou source ;
- transformer une estimation en fait ;
- garantir un résultat ou un gain ;
- recommander une mise.

Les erreurs suivantes restent structurées RFC 9457 et ne sont jamais
masquées par un résultat mock :

- match introuvable (404)
- prédiction / PIT indisponible (422)
- artefact modèle introuvable (503)
- cutoff invalide (400)
- fuite temporelle (409)

## Versioning

- analyste : `ai-analyst-0.1`
- Value Engine : `value-engine-0.1`
- modèle : `football-elo-v1-candidate`

Ces versions restent distinctes.

## Intégration frontend

Régénérer les types :

```bash
npm run generate:api-types --prefix apps/web
```

La page UI n'est pas livrée dans V0.1. Consommer
`GET /football/ai-analyst/{match_id}` derrière la `DataSource` existante,
afficher `data_mode`, `model_status`, `missing` et les champs nullables
sans les remplacer par zéro.
