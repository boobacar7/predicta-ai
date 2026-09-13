import { MOCK_NOW_ISO } from "@/data/mock/clock";
import type { FootballModelPrediction, FootballValueAnalysis } from "@/types/api";

/**
 * Canonical football engine fixtures for Lincoln, copied from the validated
 * backend case. Figures are stored as the services publish them. The UI must
 * not recompute a probability, implied probability, no-vig, edge or EV.
 */

export const LINCOLN_MATCH_ID = "mth_football-sportmonks-19719892";
export const LINCOLN_KICKOFF = "2026-07-07T16:00:00Z";
export const FOOTBALL_MODEL_VERSION = "football-elo-v1-candidate";
export const FOOTBALL_DATASET_VERSION = "football-1x2-history-0.3";
export const FOOTBALL_FEATURE_SCHEMA_VERSION = "football-1x2-features-0.3";
export const VALUE_ENGINE_VERSION = "value-engine-0.1";
export const MOCK_ODDS_SOURCE = "predicta-mock-odds-v0.1";

const HOME_PROBABILITY = 0.4165;
const DRAW_PROBABILITY = 0.27088512002991153;
const AWAY_PROBABILITY = 0.31261487997008847;

export const lincolnFootballPrediction: FootballModelPrediction = {
  match_id: LINCOLN_MATCH_ID,
  sport: "football",
  market: "1X2",
  home_probability: HOME_PROBABILITY,
  draw_probability: DRAW_PROBABILITY,
  away_probability: AWAY_PROBABILITY,
  model_version: FOOTBALL_MODEL_VERSION,
  dataset_version: FOOTBALL_DATASET_VERSION,
  feature_schema_version: FOOTBALL_FEATURE_SCHEMA_VERSION,
  model_status: "candidate",
  cutoff_at: LINCOLN_KICKOFF,
  cutoff_policy: "pre_kickoff",
  generated_at: MOCK_NOW_ISO,
};

/**
 * Lincoln 1X2 market as the Value Engine publishes it for the candidate model.
 *
 * Odds HOME 2.00 / DRAW 4.00 / AWAY 5.00 (sum of raw implied = 0.95).
 * HOME is the highest model probability; AWAY has the highest theoretical EV.
 */
export const lincolnFootballValue: FootballValueAnalysis = {
  match_id: LINCOLN_MATCH_ID,
  sport: "football",
  market: "1X2",
  prediction: {
    home_probability: HOME_PROBABILITY,
    draw_probability: DRAW_PROBABILITY,
    away_probability: AWAY_PROBABILITY,
  },
  odds: {
    bookmaker: "Fictional Sportsbook",
    provider_id: MOCK_ODDS_SOURCE,
    home_odds: 2,
    draw_odds: 4,
    away_odds: 5,
    collected_at: "2026-07-07T14:59:00Z",
    available_at: "2026-07-07T15:00:00Z",
  },
  market_probabilities: {
    overround: 0.95,
    home: {
      implied_probability: 0.5,
      no_vig_probability: 0.5263157894736842,
    },
    draw: {
      implied_probability: 0.25,
      no_vig_probability: 0.2631578947368421,
    },
    away: {
      implied_probability: 0.2,
      no_vig_probability: 0.21052631578947367,
    },
  },
  value: {
    home: { edge: -0.0835, ev: -0.167 },
    draw: { edge: 0.02088512002991153, ev: 0.08354048011964612 },
    away: { edge: 0.11261487997008847, ev: 0.5630743998504424 },
  },
  metadata: {
    value_engine_version: VALUE_ENGINE_VERSION,
    model_version: FOOTBALL_MODEL_VERSION,
    model_status: "candidate",
    dataset_version: FOOTBALL_DATASET_VERSION,
    feature_schema_version: FOOTBALL_FEATURE_SCHEMA_VERSION,
    odds_source: MOCK_ODDS_SOURCE,
    cutoff_at: LINCOLN_KICKOFF,
    generated_at: MOCK_NOW_ISO,
    data_mode: "mock",
  },
};

export function getFootballPredictionFixture(matchId: string): FootballModelPrediction | undefined {
  if (matchId === LINCOLN_MATCH_ID) {
    return lincolnFootballPrediction;
  }
  return undefined;
}

export function getFootballValueFixture(matchId: string): FootballValueAnalysis | undefined {
  if (matchId === LINCOLN_MATCH_ID) {
    return lincolnFootballValue;
  }
  return undefined;
}
