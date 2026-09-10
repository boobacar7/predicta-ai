import { MOCK_NOW_ISO, isoHoursFromNow } from "@/data/mock/clock";
import type { AiPick, AiPickExclusion, AiPicksMetadata } from "@/types/api";

/**
 * Fixtures for `GET /football/ai-picks`.
 *
 * Shapes are copied from a real response of the engine, so the mock and HTTP
 * sources stay interchangeable. Leagues are the fictional ones already used by
 * the catalogue fixtures, and `odds_source` names a mock provider rather than a
 * bookmaker: no real market price is implied anywhere in this file.
 *
 * Derived fields are stored as the engine would publish them, never recomputed
 * by the UI. They satisfy the documented identities within rounding:
 *
 *   implied_probability = 1 / odds
 *   no_vig_probability  = implied / sum(implied over the 1X2 market)
 *   edge                = model_probability - implied_probability
 *   ev                  = model_probability * odds - 1
 *   opportunity_score   = ev + edge
 *
 * `ai-picks.test.ts` enforces these, so a fixture cannot drift into numbers the
 * engine could never produce.
 */

const MODEL_VERSION = "football-elo-v1-candidate";
const ODDS_SOURCE = "predicta-mock-odds-v0.1";
const CUTOFF_AT = isoHoursFromNow(6);

type PickFacts = Pick<
  AiPick,
  | "match_id"
  | "league"
  | "selection"
  | "model_probability"
  | "odds"
  | "implied_probability"
  | "no_vig_probability"
  | "edge"
  | "ev"
  | "opportunity_score"
  | "rank"
>;

function pick(facts: PickFacts): AiPick {
  return {
    sport: "football",
    market: "1X2",
    odds_source: ODDS_SOURCE,
    model_version: MODEL_VERSION,
    model_status: "candidate",
    value_engine_version: "value-engine-0.1",
    ai_picks_version: "ai-picks-0.1",
    cutoff_at: CUTOFF_AT,
    generated_at: MOCK_NOW_ISO,
    data_mode: "mock",
    status: "eligible",
    ...facts,
  };
}

/**
 * Ordered exactly as the engine ranks: opportunity_score descending.
 *
 * Market context, so the no-vig figures are auditable:
 * - Northgate / Harbor      HOME 2.00, DRAW 4.00, AWAY 5.00 (sum implied 0.950)
 * - Silverpark / Westbridge HOME 2.15, DRAW 3.60, AWAY 3.50 (sum implied 1.029)
 * - Castleford / Riverton   HOME 2.60, DRAW 3.40, AWAY 2.80 (sum implied 1.036)
 */
export const aiPicks: AiPick[] = [
  pick({
    match_id: "mth_mock_northgate_harbor",
    league: "Continental Premier",
    selection: "AWAY",
    model_probability: 0.3126,
    odds: 5,
    implied_probability: 0.2,
    no_vig_probability: 0.2105,
    edge: 0.1126,
    ev: 0.563,
    opportunity_score: 0.6756,
    rank: 1,
  }),
  pick({
    match_id: "mth_mock_silverpark_westbridge",
    league: "Continental Premier",
    selection: "HOME",
    model_probability: 0.5412,
    odds: 2.15,
    implied_probability: 0.4651,
    no_vig_probability: 0.4522,
    edge: 0.0761,
    ev: 0.1636,
    opportunity_score: 0.2397,
    rank: 2,
  }),
  pick({
    match_id: "mth_mock_castleford_riverton",
    league: "Northern Championship",
    selection: "AWAY",
    model_probability: 0.3894,
    odds: 2.8,
    implied_probability: 0.3571,
    no_vig_probability: 0.3448,
    edge: 0.0323,
    ev: 0.0903,
    opportunity_score: 0.1226,
    rank: 3,
  }),
  pick({
    match_id: "mth_mock_northgate_harbor",
    league: "Continental Premier",
    selection: "DRAW",
    model_probability: 0.271,
    odds: 4,
    implied_probability: 0.25,
    no_vig_probability: 0.2632,
    edge: 0.021,
    ev: 0.084,
    opportunity_score: 0.105,
    rank: 4,
  }),
];

/**
 * Rejected selections.
 *
 * They matter as much as the picks: a page emptied by thresholds is a result,
 * and only the exclusions explain which rule rejected what.
 */
export const aiPickExclusions: AiPickExclusion[] = [
  {
    match_id: "mth_mock_northgate_harbor",
    league: "Continental Premier",
    market: "1X2",
    selection: "HOME",
    status: "excluded",
    reason: "negative_ev",
    detail: "Expected value is negative.",
  },
  {
    match_id: "mth_mock_silverpark_westbridge",
    league: "Continental Premier",
    market: "1X2",
    selection: "DRAW",
    status: "excluded",
    reason: "negative_edge",
    detail: "Model probability is below the implied probability.",
  },
  {
    match_id: "mth_mock_eastfield_lakeside",
    league: "Northern Championship",
    market: "1X2",
    selection: null,
    status: "excluded",
    reason: "incomplete_market",
    detail: "The 1X2 market is missing at least one selection at the cutoff.",
  },
  {
    match_id: "mth_mock_castleford_riverton",
    league: "Northern Championship",
    market: "1X2",
    selection: "HOME",
    status: "excluded",
    reason: "stale_odds",
    detail: "Odds snapshot is older than the maximum accepted age.",
  },
];

/**
 * Kickoff of each candidate, kept out of the payload on purpose.
 *
 * The engine resolves kickoffs internally to honour `?date=`, but does not
 * publish them on `AiPick`. Mirroring that split here keeps the mock honest:
 * the date filter can work while the UI still has no kickoff to display.
 */
export const mockCandidateKickoffs: Readonly<Record<string, string>> = {
  mth_mock_northgate_harbor: isoHoursFromNow(6),
  mth_mock_silverpark_westbridge: isoHoursFromNow(9),
  mth_mock_castleford_riverton: isoHoursFromNow(30),
  mth_mock_eastfield_lakeside: isoHoursFromNow(32),
};

export const aiPicksMetadata: AiPicksMetadata = {
  ai_picks_version: "ai-picks-0.1",
  scoring_formula: "opportunity_score = EV + Edge",
  ranking_order: "score DESC, EV DESC, edge DESC, freshness DESC, match_id ASC, selection ASC",
  minimum_edge: 0,
  minimum_ev: 0,
  minimum_model_probability: 0,
  maximum_odds_age_seconds: 86_400,
  evaluated_matches: 5,
  eligible_opportunities: aiPicks.length,
  excluded_opportunities: aiPickExclusions.length,
  candidate_model_allowed: true,
};
