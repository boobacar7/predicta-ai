import type {
  AiPicksFilters,
  AiPicksResult,
  AnalystSession,
  FootballAiAnalystReport,
  FootballModelPrediction,
  FootballValueAnalysis,
  CatalogFilters,
  DashboardSnapshot,
  Envelope,
  League,
  LeagueDetail,
  MatchDetailResponse,
  MatchFilters,
  MatchSummary,
  PerformanceReport,
  Pick,
  Player,
  PlayerDetail,
  Sport,
  Team,
  TeamDetail,
  ValueOpportunity,
} from "@/types/api";

export interface ListResult<T> {
  items: T[];
  total: number;
}

/** How the active source resolved its reads, surfaced for diagnostics only. */
export type DataSourceKind = "mock" | "http" | "hybrid";

/**
 * The single boundary every view reads through.
 *
 * Each method maps 1:1 onto an endpoint in docs/architecture.md §16, and takes
 * only parameters that endpoint accepts. Mock-only concerns (scenario selection,
 * fixture latency) are bound when the source is constructed, never passed per
 * call, so `MockDataSource` and `HttpDataSource` stay interchangeable.
 *
 * Every method rejects with a `DataSourceError` from `@/lib/api/errors`.
 */
export interface DataSource {
  readonly kind: DataSourceKind;

  getDashboard(): Promise<Envelope<DashboardSnapshot>>;
  getSports(): Promise<Envelope<Sport[]>>;

  getLeagues(filters?: CatalogFilters): Promise<Envelope<ListResult<League>>>;
  getLeague(id: string): Promise<Envelope<LeagueDetail>>;

  getMatches(filters?: MatchFilters): Promise<Envelope<ListResult<MatchSummary>>>;
  /**
   * Returns `MatchDetail` for a projected match, or `HistoricalMatchIdentity`
   * for an id that only exists in the point-in-time archive. Callers must
   * discriminate; the two shapes share no statistics.
   */
  getMatch(id: string): Promise<Envelope<MatchDetailResponse>>;

  getPicks(filters?: MatchFilters): Promise<Envelope<ListResult<Pick>>>;

  /**
   * `GET /football/ai-picks`.
   *
   * Returns its own result shape rather than a `ListResult`: the engine also
   * publishes structured exclusions and the thresholds it applied, and both are
   * needed to explain an empty page honestly.
   */
  getFootballAiPicks(filters?: AiPicksFilters): Promise<Envelope<AiPicksResult>>;

  /**
   * `GET /football/predictions/{match_id}`.
   *
   * Candidate 1X2 probabilities. The UI must not infer a favorite from them.
   */
  getFootballPrediction(
    matchId: string,
    cutoffAt?: string,
  ): Promise<Envelope<FootballModelPrediction>>;

  /**
   * `GET /football/value/{match_id}`.
   *
   * Canonical Value Engine analysis. There is no list route: the engine
   * evaluates one match at a time. Distinct from legacy `GET /value`.
   */
  getFootballValue(matchId: string, cutoffAt?: string): Promise<Envelope<FootballValueAnalysis>>;

  /**
   * Legacy `GET /value` catalogue. Not the football Value Engine.
   * Kept so the prototype resource can still be routed independently.
   */
  getValue(filters?: MatchFilters): Promise<Envelope<ListResult<ValueOpportunity>>>;
  getPerformance(): Promise<Envelope<PerformanceReport>>;

  getTeams(filters?: CatalogFilters): Promise<Envelope<ListResult<Team>>>;
  getTeam(id: string): Promise<Envelope<TeamDetail>>;
  getPlayers(filters?: CatalogFilters): Promise<Envelope<ListResult<Player>>>;
  getPlayer(id: string): Promise<Envelope<PlayerDetail>>;

  getAnalystSession(matchId: string, question?: string): Promise<Envelope<AnalystSession>>;

  /**
   * `GET /football/ai-analyst/{match_id}`.
   *
   * Optional `cutoff_at` is forwarded as a query parameter. The report is
   * explanatory only: it never chooses a wager.
   */
  getFootballAiAnalyst(
    matchId: string,
    cutoffAt?: string,
  ): Promise<Envelope<FootballAiAnalystReport>>;
}

/** Read method names, used to route each resource independently. */
export type DataSourceMethod = Exclude<keyof DataSource, "kind">;
