/**
 * Temporary API types for the UI prototype.
 *
 * They follow the future OpenAPI snake_case contract described in AGENTS.md
 * and docs/architecture.md. The Frontend agent must replace this file with
 * generated types from contracts/openapi.yaml when that contract exists.
 * Do not silently diverge from the documented endpoints.
 */

export type DataMode = "mock" | "live";
export type SportCode = "football" | "basketball" | "tennis";
export type AvailabilityStatus = "available" | "unavailable" | "partial" | "stale";
export type ConfidenceLevel = "low" | "medium" | "high";
export type MatchStatus = "scheduled" | "live" | "finished" | "postponed";
export type FreshnessLevel = "fresh" | "acceptable" | "stale";
export type MockScenario = "success" | "empty" | "partial" | "stale" | "error";

export interface Envelope<T> {
  data_mode: DataMode;
  generated_at: string;
  request_id: string;
  data: T;
}

export interface DataQuality {
  availability: AvailabilityStatus;
  source: string | null;
  observed_at: string | null;
  freshness: FreshnessLevel | null;
  note: string | null;
}

export interface IdentifiedEntity {
  id: string;
  name: string;
}

export interface Sport extends IdentifiedEntity {
  code: SportCode;
}

export interface League extends IdentifiedEntity {
  sport: SportCode;
  country: string;
  season: string;
  tier: number;
}

export interface Team extends IdentifiedEntity {
  short_name: string;
  sport: SportCode;
  league_id: string;
  abbreviation: string;
}

export interface Player extends IdentifiedEntity {
  sport: SportCode;
  team_id: string | null;
  position: string | null;
  country: string;
}

export interface Scoreline {
  home: number | null;
  away: number | null;
  quality: DataQuality;
}

export interface MatchSummary {
  id: string;
  sport: SportCode;
  league: League;
  home: Team;
  away: Team;
  kickoff_at: string;
  status: MatchStatus;
  venue: string | null;
  score: Scoreline;
  prediction_preview: PredictionPreview | null;
  value_preview: ValuePreview | null;
  quality: DataQuality;
}

export interface MatchDetail extends MatchSummary {
  timeline: MatchEvent[];
  stats: MatchStatistic[];
  odds: OddsSnapshot | null;
  prediction: PredictionDetail | null;
  form: TeamFormSide[];
  unavailable_fields: UnavailableField[];
}

export interface MatchEvent {
  id: string;
  minute: number | null;
  type: string;
  label: string;
  team_id: string | null;
  quality: DataQuality;
}

export interface MatchStatistic {
  key: string;
  label: string;
  home_value: number | null;
  away_value: number | null;
  unit: string | null;
  quality: DataQuality;
}

export interface UnavailableField {
  field: string;
  reason: string;
}

export interface TeamFormSide {
  team_id: string;
  results: Array<"W" | "D" | "L" | null>;
  quality: DataQuality;
}

export interface ProbabilityOutcome {
  selection: string;
  label: string;
  model_probability: number | null;
  calibrated_probability: number | null;
  quality: DataQuality;
}

export interface PredictionPreview {
  model_version: string;
  market: string;
  confidence: ConfidenceLevel;
  leading_selection: string;
  leading_probability: number | null;
  cutoff_at: string;
  outcomes: ProbabilityOutcome[];
  quality: DataQuality;
}

export interface PredictionFactor {
  id: string;
  label: string;
  direction: "home" | "away" | "neutral";
  weight: "low" | "medium" | "high";
  detail: string;
  quality: DataQuality;
}

export interface PredictionDetail {
  id: string;
  match_id: string;
  market: string;
  model_family: string;
  model_version: string;
  calibrator_version: string;
  feature_set_version: string;
  cutoff_at: string;
  confidence: ConfidenceLevel;
  outcomes: ProbabilityOutcome[];
  factors: PredictionFactor[];
  quality: DataQuality;
}

export interface OddsSelection {
  selection: string;
  label: string;
  decimal_odds: number | null;
  implied_probability_raw: number | null;
  no_vig_probability: number | null;
  quality: DataQuality;
}

export interface OddsSnapshot {
  id: string;
  match_id: string;
  market: string;
  bookmaker: string;
  provider: string;
  observed_at: string;
  overround: number | null;
  selections: OddsSelection[];
  quality: DataQuality;
}

export interface ValuePreview {
  selection: string;
  edge: number | null;
  expected_value: number | null;
  formula_version: string;
  quality: DataQuality;
}

export interface ValueOpportunity {
  id: string;
  match: MatchSummary;
  market: string;
  selection: string;
  selection_label: string;
  calibrated_probability: number | null;
  decimal_odds: number | null;
  implied_probability_raw: number | null;
  no_vig_probability: number | null;
  overround: number | null;
  edge_raw: number | null;
  edge_no_vig: number | null;
  expected_value: number | null;
  formula_version: string;
  odds_observed_at: string | null;
  prediction_cutoff_at: string | null;
  quality: DataQuality;
}

export interface Pick {
  id: string;
  match: MatchSummary;
  market: string;
  selection: string;
  selection_label: string;
  calibrated_probability: number | null;
  confidence: ConfidenceLevel;
  rationale: string;
  criteria: string;
  model_version: string;
  published_at: string;
  quality: DataQuality;
}

export interface Insight {
  id: string;
  title: string;
  body: string;
  kind: "model" | "data" | "value" | "caution";
  href: string | null;
  quality: DataQuality;
}

export interface MetricPoint {
  label: string;
  value: number | null;
  quality: DataQuality;
}

export interface DashboardSnapshot {
  headline: string;
  sports: Sport[];
  matches_today: MatchSummary[];
  picks: Pick[];
  value_opportunities: ValueOpportunity[];
  insights: Insight[];
  model_health: ModelHealthSummary;
}

export interface ModelHealthSummary {
  model_version: string;
  sport: SportCode;
  window_label: string;
  accuracy: number | null;
  log_loss: number | null;
  brier_score: number | null;
  ece: number | null;
  /** Backtest ROI, expressed as a ratio. Theoretical, never a promised return. */
  theoretical_roi: number | null;
  /** Worst peak-to-trough decline observed in the same backtest, as a ratio. */
  theoretical_max_drawdown: number | null;
  prediction_count: number;
  quality: DataQuality;
}

export interface PerformanceSeriesPoint {
  period: string;
  log_loss: number | null;
  brier_score: number | null;
  accuracy: number | null;
  theoretical_roi: number | null;
}

export interface CalibrationBucket {
  predicted: number;
  observed: number | null;
  count: number;
}

export interface PerformanceReport {
  summary: ModelHealthSummary;
  series: PerformanceSeriesPoint[];
  calibration: CalibrationBucket[];
  notes: string[];
}

export interface LeagueDetail {
  league: League;
  standing: StandingRow[];
  recent_matches: MatchSummary[];
  unavailable_fields: UnavailableField[];
}

export interface StandingRow {
  rank: number | null;
  team: Team;
  played: number | null;
  points: number | null;
  goal_diff: number | null;
  quality: DataQuality;
}

export interface TeamDetail {
  team: Team;
  league: League;
  recent_matches: MatchSummary[];
  stats: NamedStat[];
  unavailable_fields: UnavailableField[];
}

export interface PlayerDetail {
  player: Player;
  team: Team | null;
  stats: NamedStat[];
  recent_mentions: string[];
  unavailable_fields: UnavailableField[];
}

export interface NamedStat {
  key: string;
  label: string;
  value: number | null;
  unit: string | null;
  quality: DataQuality;
}

export interface Fact {
  id: string;
  label: string;
  value: string;
  unit: string | null;
  source: string;
  observed_at: string;
  availability: AvailabilityStatus;
}

export interface FactPack {
  id: string;
  match_id: string;
  generated_at: string;
  facts: Fact[];
}

export interface AnalystMessage {
  id: string;
  role: "user" | "analyst";
  body: string;
  cited_fact_ids: string[];
  created_at: string;
}

export interface AnalystSession {
  match_id: string;
  fact_pack: FactPack;
  messages: AnalystMessage[];
  llm_model: string;
  prompt_version: string;
  disclaimer: string;
}

/* -------------------------------------------------------------------------
 * AI Picks Engine (ai-picks-0.1)
 *
 * Mirrors `AiPick`, `AiPickExclusion`, `AiPicksMetadata` and `AiPicksResult`
 * in contracts/openapi.yaml, which declare `additionalProperties: false`.
 * Nothing here may be widened locally: a field the engine does not publish is
 * a gap to raise with the Backend agent, never one to fill in the UI.
 *
 * Ratios are raw decimals: `0.072` means 7.2 points.
 * ---------------------------------------------------------------------- */

export type FootballModelStatus = "candidate" | "champion" | "production";
export type Football1x2Selection = "HOME" | "DRAW" | "AWAY";

export type AiPickExclusionReason =
  | "negative_ev"
  | "negative_edge"
  | "below_minimum_ev"
  | "below_minimum_edge"
  | "below_minimum_model_probability"
  | "invalid_odds"
  | "incomplete_market"
  | "prediction_unavailable"
  | "pit_unavailable"
  | "invalid_prediction"
  | "invalid_value"
  | "stale_odds";

/**
 * One ranked opportunity.
 *
 * The engine resolves team identity and kickoff internally but does not
 * publish them, so a pick can only be identified by `match_id` and `league`.
 */
export interface AiPick {
  match_id: string;
  sport: "football";
  league: string;
  market: "1X2";
  selection: Football1x2Selection;
  model_probability: number;
  odds: number;
  implied_probability: number;
  no_vig_probability: number;
  edge: number;
  ev: number;
  opportunity_score: number;
  rank: number;
  odds_source: string;
  model_version: string;
  model_status: FootballModelStatus;
  value_engine_version: string;
  ai_picks_version: "ai-picks-0.1";
  cutoff_at: string;
  generated_at: string;
  data_mode: DataMode;
  status: "eligible";
}

/** A rejected selection. The engine never drops a candidate silently. */
export interface AiPickExclusion {
  match_id: string;
  league: string;
  market: "1X2";
  selection: Football1x2Selection | null;
  status: "excluded";
  reason: AiPickExclusionReason;
  detail: string;
}

export interface AiPicksMetadata {
  ai_picks_version: "ai-picks-0.1";
  scoring_formula: "opportunity_score = EV + Edge";
  ranking_order: string;
  minimum_edge: number;
  minimum_ev: number;
  minimum_model_probability: number;
  maximum_odds_age_seconds: number;
  evaluated_matches: number;
  eligible_opportunities: number;
  excluded_opportunities: number;
  candidate_model_allowed: boolean;
}

export interface AiPicksResult {
  items: AiPick[];
  exclusions: AiPickExclusion[];
  total: number;
  limit: number;
  offset: number;
  metadata: AiPicksMetadata;
}

/**
 * Query parameters of `GET /football/ai-picks`.
 *
 * There is no sport parameter: the engine serves football only, as declared by
 * the `sport` enum in the contract.
 */
export interface AiPicksFilters {
  date?: string;
  league?: string;
  limit?: number;
  offset?: number;
  min_edge?: number;
  min_ev?: number;
}

export interface MatchFilters {
  sport?: SportCode | "all";
  league_id?: string | "all";
  date?: string;
  status?: MatchStatus | "all";
}

export interface CatalogFilters {
  sport?: SportCode | "all";
  query?: string;
}
