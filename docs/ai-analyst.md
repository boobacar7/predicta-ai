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
  → AnalystEvidence (faits whitelistés)
  → GroundedStatement (faits + narration)
  → AnalystProvider.generate_analysis(context)
  → assert_grounded
  → GET /api/v1/football/ai-analyst/{match_id}
```

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

Quatre couches restent séparées :

1. **faits** issus du contexte (`AnalystEvidence`) : identité, probabilités,
   cotes, edge, EV, versions, cutoff, `data_mode` ;
2. **evidence** : whitelist immuable. Un `evidence_id` inconnu est refusé ;
3. **narration** : `GroundedStatement.statement` est une interprétation.
   `factual_claims` doivent reproduire un champ evidence disponible.
   Le texte rendu (`summary`, forces, risques, `confidence.basis`) est
   rescanné : tout nombre, cote, EV, équipe ou date non présents dans le
   contexte est rejeté. La prose qualitative sans fait nouveau reste
   autorisée ;
4. **frontière provider** : le provider raconte le contexte. Il ne possède
   aucune donnée. `DeterministicAnalystProvider` émet des
   `GroundedStatement` puis `render_statements`.
   `LLMAnalystProvider` fait de même : il ne retourne que des statements
   liés à des `evidence_ids`. Les claims numériques sont reconstruits
   depuis `AnalystEvidence`, jamais depuis le LLM.

Les DTOs `prediction` et `value` sont reconstruits par le service depuis
`AnalystContext`, jamais depuis le texte du provider.

## Provider LLM (narrator)

`AnalystProvider` est le port. `LLMAnalystProvider.generate_analysis(context)`
reçoit uniquement le contexte validé. **LLM output ≠ source of truth.**

Flux :

```text
AnalystContext.evidence()
  → prompt (faits whitelistés uniquement)
  → LLM JSON { statements: [{ statement, evidence_ids }] }
  → parse / schema extra=forbid
  → evidence_ids + claims
  → assert_statements_grounded
  → summary
  → assert_grounded
  → DTO
```

Le LLM n'a pas le droit de définir `probabilities`, `odds`, `edge`, `EV`,
`model_version`, `dataset_version`, `cutoff_at` ou `data_mode`. Toute
sortie malformée, expirée, non grounded ou qui confond `model_favorite` et
`value_selection` retombe sur `DeterministicAnalystProvider`.

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
→ rejet, puis fallback déterministe.

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
