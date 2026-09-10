import { HttpClient, type HttpClientOptions } from "@/data/http/client";
import type {
  AiPicksFilters,
  AiPicksResult,
  AnalystSession,
  CatalogFilters,
  DashboardSnapshot,
  League,
  LeagueDetail,
  MatchDetail,
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
import type { DataSource, ListResult } from "@/types/datasource";

/**
 * Reads the PREDICTA API over HTTP.
 *
 * Routes follow docs/architecture.md §16 under the `/api/v1` prefix. This source
 * is inert until a resource is pointed at `http` through configuration, so it can
 * be wired endpoint by endpoint without touching a single view.
 *
 * Known divergence to reconcile when `contracts/openapi.yaml` lands: the API list
 * has no aggregate dashboard route, so `GET /dashboard` is assumed here. It is the
 * only path in this file not already documented in the contract.
 */
export class HttpDataSource implements DataSource {
  readonly kind = "http" as const;

  private readonly client: HttpClient;

  constructor(options: HttpClientOptions) {
    this.client = new HttpClient(options);
  }

  getDashboard() {
    return this.client.get<DashboardSnapshot>("/dashboard");
  }

  getSports() {
    return this.client.get<Sport[]>("/sports");
  }

  getLeagues(filters: CatalogFilters = {}) {
    return this.client.get<ListResult<League>>("/leagues", catalogParams(filters));
  }

  getLeague(id: string) {
    return this.client.get<LeagueDetail>(`/leagues/${encodeURIComponent(id)}`);
  }

  getMatches(filters: MatchFilters = {}) {
    return this.client.get<ListResult<MatchSummary>>("/matches", matchParams(filters));
  }

  getMatch(id: string) {
    return this.client.get<MatchDetail>(`/matches/${encodeURIComponent(id)}`);
  }

  getPicks(filters: MatchFilters = {}) {
    return this.client.get<ListResult<Pick>>("/picks", matchParams(filters));
  }

  getFootballAiPicks(filters: AiPicksFilters = {}) {
    return this.client.get<AiPicksResult>("/football/ai-picks", aiPicksParams(filters));
  }

  getValue(filters: MatchFilters = {}) {
    return this.client.get<ListResult<ValueOpportunity>>("/value", matchParams(filters));
  }

  getPerformance() {
    return this.client.get<PerformanceReport>("/performance");
  }

  getTeams(filters: CatalogFilters = {}) {
    return this.client.get<ListResult<Team>>("/teams", catalogParams(filters));
  }

  getTeam(id: string) {
    return this.client.get<TeamDetail>(`/teams/${encodeURIComponent(id)}`);
  }

  getPlayers(filters: CatalogFilters = {}) {
    return this.client.get<ListResult<Player>>("/players", catalogParams(filters));
  }

  getPlayer(id: string) {
    return this.client.get<PlayerDetail>(`/players/${encodeURIComponent(id)}`);
  }

  getAnalystSession(matchId: string, question?: string) {
    return this.client.post<AnalystSession>("/ai/analyze", {
      match_id: matchId,
      question: question ?? null,
    });
  }
}

function catalogParams(filters: CatalogFilters) {
  return { sport: filters.sport, query: filters.query };
}

function matchParams(filters: MatchFilters) {
  return {
    sport: filters.sport,
    league_id: filters.league_id,
    date: filters.date,
    status: filters.status,
  };
}

/**
 * Parameter names are the engine's own, not the generic match filter names:
 * the route takes `league` (a name) rather than `league_id`, and has no `sport`.
 */
function aiPicksParams(filters: AiPicksFilters) {
  return {
    date: filters.date,
    league: filters.league,
    limit: filters.limit,
    offset: filters.offset,
    min_edge: filters.min_edge,
    min_ev: filters.min_ev,
  };
}
