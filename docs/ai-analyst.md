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
  → AnalystProvider.generate_analysis(context)
  → GET /api/v1/football/ai-analyst/{match_id}
```

Le LLM, s'il est branché plus tard, reste strictement downstream du contexte.
`DeterministicAnalystProvider` est le provider par défaut et ne nécessite
aucune clé externe.

## Contrat

```text
GET /api/v1/football/ai-analyst/{match_id}?cutoff_at=<RFC3339>
```

La réponse enveloppe standard porte `data_mode`, `generated_at` et
`request_id`. `data` contient :

- identité : `match_id`, `home_team`, `away_team`, `league`, `kickoff_at` ;
- `prediction` : probabilités 1X2, versions, statut, cutoff ;
- `value` : sélection expliquée, cote, probabilités implicites, edge, EV,
  ou `availability=unavailable` ;
- `analyst` : résumé, facteurs, forces, risques, confiance, qualité,
  `analysis_version=ai-analyst-0.1`.

`home_team` et `away_team` sont requis mais nullables. Un nom absent n'est
jamais remplacé.

La sélection value expliquée est l'issue de plus haute probabilité modèle,
avec un tie-break `HOME`, `DRAW`, `AWAY`. Ce n'est pas une recommandation.

## Provenance

Chaque facteur porte un `source` interne :

- `football-prediction-service`
- `value-engine-0.1`
- identifiant du snapshot de cotes lorsqu'un âge de cote est exposé

Le résumé n'insère que des nombres présents dans le contexte. S'il n'y a pas
de cote, le texte dit que l'implicite, l'edge et l'EV sont absents.

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
2. `medium` si modèle candidat, identité complète et value disponible ;
3. `low` dans tous les autres cas (candidat + lacune, mock, value absente,
   identité partielle).

La magnitude des probabilités n'entre jamais dans cette règle. Avec le
candidat actuel, `high` n'est pas émis.

## Provider déterministe

`DeterministicAnalystProvider.generate_analysis(context)` est une fonction
pure : pas d'horloge, pas d'I/O, pas d'aléa. Deux appels sur le même
contexte produisent le même objet. `generated_at` est copié du contexte,
lui-même fixé par l'horloge injectable du service.

## Futur provider LLM

`AnalystProvider` est le port. Un provider LLM pourra implémenter
`generate_analysis(context)` plus tard. Il recevra uniquement le contexte
validé, devra citer ces faits, et devra échouer plutôt que combler une
lacune. Aucune dépendance LLM n'est ajoutée dans V0.1.

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
