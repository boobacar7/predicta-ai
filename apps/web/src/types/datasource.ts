import type {
  AnalystSession,
  CatalogFilters,
  DashboardSnapshot,
  Envelope,
  League,
  LeagueDetail,
  MatchDetail,
  MatchFilters,
  MatchSummary,
  MockScenario,
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

export interface DataSource {
  readonly mode: "mock" | "http";
  getDashboard(scenario?: MockScenario): Promise<Envelope<DashboardSnapshot>>;
  getSports(): Promise<Envelope<Sport[]>>;
  getLeagues(filters?: CatalogFilters): Promise<Envelope<ListResult<League>>>;
  getLeague(id: string): Promise<Envelope<LeagueDetail>>;
  getMatches(filters?: MatchFilters, scenario?: MockScenario): Promise<Envelope<ListResult<MatchSummary>>>;
  getMatch(id: string, scenario?: MockScenario): Promise<Envelope<MatchDetail>>;
  getPicks(filters?: MatchFilters, scenario?: MockScenario): Promise<Envelope<ListResult<Pick>>>;
  getValue(
    filters?: MatchFilters,
    scenario?: MockScenario,
  ): Promise<Envelope<ListResult<ValueOpportunity>>>;
  getPerformance(scenario?: MockScenario): Promise<Envelope<PerformanceReport>>;
  getTeams(filters?: CatalogFilters): Promise<Envelope<ListResult<Team>>>;
  getTeam(id: string): Promise<Envelope<TeamDetail>>;
  getPlayers(filters?: CatalogFilters): Promise<Envelope<ListResult<Player>>>;
  getPlayer(id: string): Promise<Envelope<PlayerDetail>>;
  getAnalystSession(matchId: string, question?: string): Promise<Envelope<AnalystSession>>;
}
