import { MOCK_NOW_ISO } from "@/data/mock/clock";
import type { FootballAiAnalystReport, FootballAnalystExplanation } from "@/types/api";

/**
 * Fixtures for `GET /football/ai-analyst/{match_id}`.
 *
 * The default report is the validated Lincoln case: HOME is the model favorite
 * while AWAY is the highest theoretical EV. Figures are stored as the backend
 * publishes them. The UI must not recompute a favorite, an EV, or a ranking.
 */

export const LINCOLN_ANALYST_MATCH_ID = "mth_football-sportmonks-19719892";
export const ANALYST_MISSING_IDENTITY_ID = "mth_analyst_missing_identity";
export const ANALYST_MISSING_VALUE_ID = "mth_analyst_missing_value";
export const ANALYST_MISSING_FACTORS_ID = "mth_analyst_missing_factors";
export const ANALYST_INVALID_KICKOFF_ID = "mth_analyst_invalid_kickoff";

export const LINCOLN_KICKOFF = "2026-07-07T16:00:00Z";

export const ANALYST_CONFIDENCE_RULE =
  "high requires champion + live + complete identity + available value; " +
  "candidate with complete identity and available value is medium, including mock; " +
  "candidate never emits high; " +
  "any of incomplete identity, missing value, or other metadata gap is low; " +
  "probability magnitude is never used.";

const HOME_PROBABILITY = 0.4165;
const DRAW_PROBABILITY = 0.27088512002991153;
const AWAY_PROBABILITY = 0.31261487997008847;
const HOME_ODDS = 2;
const HOME_IMPLIED = 0.5;
const HOME_NO_VIG = 0.5263157894736842;
const HOME_EDGE = -0.0835;
const HOME_EV = -0.167;

const BASE_PREDICTION = {
  home_probability: HOME_PROBABILITY,
  draw_probability: DRAW_PROBABILITY,
  away_probability: AWAY_PROBABILITY,
  model_version: "football-elo-v1-candidate",
  model_status: "candidate" as const,
  dataset_version: "football-1x2-history-0.3",
  cutoff_at: LINCOLN_KICKOFF,
  source: "football-prediction-service",
};

const AVAILABLE_VALUE = {
  availability: "available" as const,
  selection: "HOME" as const,
  value_selection: "AWAY" as const,
  odds: HOME_ODDS,
  implied_probability: HOME_IMPLIED,
  no_vig_probability: HOME_NO_VIG,
  edge: HOME_EDGE,
  ev: HOME_EV,
  value_engine_version: "value-engine-0.1",
  source: "value-engine-0.1",
};

const UNAVAILABLE_VALUE = {
  availability: "unavailable" as const,
  selection: null,
  value_selection: null,
  odds: null,
  implied_probability: null,
  no_vig_probability: null,
  edge: null,
  ev: null,
  value_engine_version: null,
  source: null,
};

function explanation(
  overrides: Partial<FootballAnalystExplanation> = {},
): FootballAnalystExplanation {
  return {
    summary:
      "Le modèle football-elo-v1-candidate attribue 41,7 % de probabilité à Lincoln Red Imps. " +
      "La probabilité implicite brute de la cote disponible est de 50,0 %. " +
      "L'écart modèle-marché (edge) est de -8,4 points. " +
      "L'espérance théorique (EV) calculée par value-engine-0.1 est de -16,7 points. " +
      "Ces valeurs sont des estimations statistiques, pas un résultat futur.",
    key_factors: [
      {
        type: "model_probability",
        label: "Probabilité modèle · HOME",
        value: HOME_PROBABILITY,
        direction: "home",
        source: "football-prediction-service",
      },
      {
        type: "model_status",
        label: "Statut du modèle",
        value: null,
        direction: "neutral",
        source: "football-prediction-service",
      },
      {
        type: "market_probability",
        label: "Probabilité implicite brute",
        value: HOME_IMPLIED,
        direction: "home",
        source: "value-engine-0.1",
      },
      {
        type: "edge",
        label: "Edge modèle-marché",
        value: HOME_EDGE,
        direction: "home",
        source: "value-engine-0.1",
      },
      {
        type: "ev",
        label: "EV théorique",
        value: HOME_EV,
        direction: "home",
        source: "value-engine-0.1",
      },
      {
        type: "data_freshness",
        label: "Âge des cotes au cutoff (secondes)",
        value: 7200,
        direction: "neutral",
        source: "predicta-mock-odds-v0.1",
      },
    ],
    strengths: [
      "Les trois probabilités 1X2 du modèle sont présentes dans le contexte validé.",
      "Une analyse value-engine-0.1 est disponible pour HOME.",
      "L'identité structurelle du match est complète.",
    ],
    risks: [
      "Le modèle football-elo-v1-candidate n'est pas promu : ses probabilités restent des estimations évaluées.",
      "Les données portent data_mode=mock et ne représentent aucun marché réel.",
      "L'EV théorique du favori du modèle est négative ; ce n'est pas un signal de mise.",
    ],
    confidence: {
      level: "medium",
      basis: "Modèle candidat avec identité complète et value disponible. Ce n'est pas une certitude.",
      rule: ANALYST_CONFIDENCE_RULE,
    },
    data_quality: {
      data_mode: "mock",
      model_status: "candidate",
      cutoff_at: LINCOLN_KICKOFF,
      freshness: "fresh",
      availability: "available",
      missing: [],
    },
    generated_at: MOCK_NOW_ISO,
    analysis_version: "ai-analyst-0.1",
    provider: "deterministic-v0.1",
    ...overrides,
  };
}

/** Canonical case: HOME favorite, AWAY best theoretical EV. */
export const lincolnAnalystReport: FootballAiAnalystReport = {
  match_id: LINCOLN_ANALYST_MATCH_ID,
  home_team: "Lincoln Red Imps",
  away_team: "Inter Club d'Escaldes",
  league: "Champions League",
  kickoff_at: LINCOLN_KICKOFF,
  model_favorite: "HOME",
  prediction: BASE_PREDICTION,
  value: AVAILABLE_VALUE,
  analyst: explanation(),
};

export const missingIdentityReport: FootballAiAnalystReport = {
  match_id: ANALYST_MISSING_IDENTITY_ID,
  home_team: null,
  away_team: null,
  league: "Champions League",
  kickoff_at: LINCOLN_KICKOFF,
  model_favorite: "HOME",
  prediction: BASE_PREDICTION,
  value: AVAILABLE_VALUE,
  analyst: explanation({
    summary:
      "Le modèle football-elo-v1-candidate attribue 41,7 % de probabilité à l'équipe à domicile. " +
      "Données explicitement indisponibles : home_team, away_team. Elles n'ont pas été complétées. " +
      "Ces valeurs sont des estimations statistiques, pas un résultat futur.",
    strengths: ["Les trois probabilités 1X2 du modèle sont présentes dans le contexte validé."],
    risks: [
      "L'identité structurelle du match est incomplète.",
      "Le modèle football-elo-v1-candidate n'est pas promu.",
    ],
    confidence: {
      level: "low",
      basis: "Confiance limitée par les métadonnées suivantes : model_status=candidate, home_team, away_team.",
      rule: ANALYST_CONFIDENCE_RULE,
    },
    data_quality: {
      data_mode: "mock",
      model_status: "candidate",
      cutoff_at: LINCOLN_KICKOFF,
      freshness: "fresh",
      availability: "partial",
      missing: ["home_team", "away_team"],
    },
  }),
};

export const missingValueReport: FootballAiAnalystReport = {
  match_id: ANALYST_MISSING_VALUE_ID,
  home_team: "Lincoln Red Imps",
  away_team: "Inter Club d'Escaldes",
  league: "Champions League",
  kickoff_at: LINCOLN_KICKOFF,
  model_favorite: "HOME",
  prediction: BASE_PREDICTION,
  value: UNAVAILABLE_VALUE,
  analyst: explanation({
    summary:
      "Le modèle football-elo-v1-candidate attribue 41,7 % de probabilité à Lincoln Red Imps. " +
      "Aucune cote PIT n'est disponible dans le contexte validé ; " +
      "aucune probabilité implicite, edge ou EV n'est affirmée. " +
      "Ces valeurs sont des estimations statistiques, pas un résultat futur.",
    key_factors: [
      {
        type: "model_probability",
        label: "Probabilité modèle · HOME",
        value: HOME_PROBABILITY,
        direction: "home",
        source: "football-prediction-service",
      },
      {
        type: "model_status",
        label: "Statut du modèle",
        value: null,
        direction: "neutral",
        source: "football-prediction-service",
      },
    ],
    strengths: [
      "Les trois probabilités 1X2 du modèle sont présentes dans le contexte validé.",
      "L'identité structurelle du match est complète.",
    ],
    risks: [
      "Aucune analyse de valeur n'est publiée pour ce cutoff.",
      "Le modèle football-elo-v1-candidate n'est pas promu.",
    ],
    confidence: {
      level: "low",
      basis: "Confiance limitée par les métadonnées suivantes : model_status=candidate, value.",
      rule: ANALYST_CONFIDENCE_RULE,
    },
    data_quality: {
      data_mode: "mock",
      model_status: "candidate",
      cutoff_at: LINCOLN_KICKOFF,
      freshness: null,
      availability: "partial",
      missing: ["value"],
    },
  }),
};

export const missingFactorsReport: FootballAiAnalystReport = {
  match_id: ANALYST_MISSING_FACTORS_ID,
  home_team: "Lincoln Red Imps",
  away_team: "Inter Club d'Escaldes",
  league: "Champions League",
  kickoff_at: LINCOLN_KICKOFF,
  model_favorite: "HOME",
  prediction: BASE_PREDICTION,
  value: AVAILABLE_VALUE,
  analyst: explanation({
    key_factors: [],
    strengths: [],
    risks: ["Aucun facteur clé n'est publié pour cette analyse."],
  }),
};

export const invalidKickoffReport: FootballAiAnalystReport = {
  ...lincolnAnalystReport,
  match_id: ANALYST_INVALID_KICKOFF_ID,
  kickoff_at: "not-a-date",
};

const REPORTS: Record<string, FootballAiAnalystReport> = {
  [LINCOLN_ANALYST_MATCH_ID]: lincolnAnalystReport,
  [ANALYST_MISSING_IDENTITY_ID]: missingIdentityReport,
  [ANALYST_MISSING_VALUE_ID]: missingValueReport,
  [ANALYST_MISSING_FACTORS_ID]: missingFactorsReport,
  [ANALYST_INVALID_KICKOFF_ID]: invalidKickoffReport,
};

export function getAnalystReportFixture(matchId: string): FootballAiAnalystReport | undefined {
  return REPORTS[matchId];
}

export const analystMatchOptions = [
  { id: LINCOLN_ANALYST_MATCH_ID, label: "Lincoln Red Imps vs Inter Club d'Escaldes" },
  { id: ANALYST_MISSING_IDENTITY_ID, label: "Identité partielle" },
  { id: ANALYST_MISSING_VALUE_ID, label: "Valeur indisponible" },
  { id: ANALYST_MISSING_FACTORS_ID, label: "Facteurs absents" },
  { id: ANALYST_INVALID_KICKOFF_ID, label: "Kickoff invalide" },
] as const;
