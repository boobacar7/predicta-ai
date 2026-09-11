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
3. Toute sortie invalide, expirée ou non grounded retombe sur
   `DeterministicAnalystProvider`.
4. Le client livré est `mock-explainer-0.1`. Aucun vendor LLM ni secret
   n'est introduit.
5. `PREDICTA_API_ANALYST_NARRATOR` reste `deterministic` par défaut.
6. Le frontend continue d'appeler `GET /api/v1/football/ai-analyst/{match_id}`.

## Conséquences

Le LLM est strictement downstream. Il ne peut pas écrire une prédiction,
une cote, un EV ou un cutoff. `analyst.provider` peut valoir `llm-v0.1`
uniquement lorsque la narration a passé `assert_grounded`.
