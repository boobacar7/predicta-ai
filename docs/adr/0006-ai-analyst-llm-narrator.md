# ADR 0006 — AI Analyst LLM narrator

- Statut : accepté
- Date : 2026-09-11
- Agent : AI Analyst / LLM Integration
- Portée : `apps/api/app/ai_analyst`, contrat `FootballAnalystExplanation.provider`.
  Aucune modification du Prediction Service, du Value Engine, de
  `HistoricalMatchIdentity` ni du frontend data layer.

## Contexte

Le grounding V0.1 est validé : `AnalystContext` → `AnalystEvidence` →
`GroundedStatement` → `assert_grounded`. Un narrator LLM peut maintenant
être ajouté sans devenir une source de vérité.

## Décisions

1. `LLMAnalystProvider` implémente le port existant `AnalystProvider`.
2. Le LLM ne retourne que `{ statements: [{ statement, evidence_ids }] }`.
   Probabilités, cotes, edge, EV, versions, cutoff et `data_mode` sont
   reconstruits depuis `AnalystContext`.
3. Toute sortie invalide, expirée, non grounded, ou toute exception
   du chemin narrator (`RuntimeError`, timeout, JSON, schema, claim,
   evidence, grounding) retombe sur `DeterministicAnalystProvider` avec un
   DTO complet. `GroundedClaim` (interne) relie chaque affirmation
   factuelle à `claim_type` + sujet + valeur + evidence. Une paraphrase
   (« above seventy », « soixante-dix », « most likely », « best value »,
   « live odds ») est une claim, pas une string interdite. Une evidence de
   cote/implicite/EV ne justifie pas une claim d'un autre type ou d'une
   autre sélection. `model_favorite` et `value_selection` restent distincts.
   Le fallback ne masque pas les erreurs PIT / Prediction Service / Value
   Engine / `ApiError`.
4. Le client livré est `mock-explainer-0.1`. Aucun vendor LLM ni secret
   n'est introduit.
5. `PREDICTA_API_ANALYST_NARRATOR` reste `deterministic` par défaut.
6. Le frontend continue d'appeler `GET /api/v1/football/ai-analyst/{match_id}`.

## Conséquences

Le LLM est un narrator. Il ne devient jamais source of truth. Le DTO
métier (`probabilities`, odds, implicite, no-vig, edge, EV, versions,
`cutoff_at`, `data_mode`, identité) est toujours reconstruit depuis
`AnalystContext`. `analyst.provider` vaut `llm-v0.1` seulement si chaque
claim a passé la validation claim/evidence. Sinon le DTO est
`deterministic-v0.1`, sans narration LLM partielle.
