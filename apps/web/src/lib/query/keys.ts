import type { AiPicksFilters, CatalogFilters, MatchFilters, MockScenario } from "@/types/api";

/**
 * Centralised query key factory.
 *
 * Keys are hierarchical so a whole resource can be invalidated by prefix, and
 * serialisable so React Query hashes them deterministically. Filters are
 * normalised to a fixed shape, which keeps a key stable regardless of how the
 * caller built its filter object.
 *
 * The scenario sits at the root: switching mock scenarios must never reuse a
 * cache entry produced by another scenario.
 */

export type NormalizedMatchFilters = Readonly<{
  sport: string;
  league_id: string;
  date: string;
  status: string;
}>;

export type NormalizedCatalogFilters = Readonly<{
  sport: string;
  query: string;
}>;

export function normalizeMatchFilters(filters: MatchFilters = {}): NormalizedMatchFilters {
  return {
    sport: filters.sport ?? "all",
    league_id: filters.league_id ?? "all",
    date: filters.date ?? "",
    status: filters.status ?? "all",
  };
}

export function normalizeCatalogFilters(filters: CatalogFilters = {}): NormalizedCatalogFilters {
  return {
    sport: filters.sport ?? "all",
    query: filters.query?.trim() ?? "",
  };
}

export type NormalizedAiPicksFilters = Readonly<{
  date: string;
  league: string;
  limit: number;
  offset: number;
  min_edge: number | null;
  min_ev: number | null;
}>;

/**
 * `min_edge` and `min_ev` normalise to `null`, never `0`.
 *
 * Omitting a threshold lets the engine apply its own default, which is not the
 * same request as pinning it to zero, and the two must not share a cache entry.
 */
export function normalizeAiPicksFilters(filters: AiPicksFilters = {}): NormalizedAiPicksFilters {
  return {
    date: filters.date ?? "",
    league: filters.league?.trim() ?? "",
    limit: filters.limit ?? DEFAULT_AI_PICKS_LIMIT,
    offset: filters.offset ?? 0,
    min_edge: filters.min_edge ?? null,
    min_ev: filters.min_ev ?? null,
  };
}

/** Matches the `AiPicksLimit` default declared in contracts/openapi.yaml. */
export const DEFAULT_AI_PICKS_LIMIT = 20;

const root = (scenario: MockScenario) => ["predicta", scenario] as const;

export const queryKeys = {
  root,

  dashboard: (scenario: MockScenario) => [...root(scenario), "dashboard"] as const,
  sports: (scenario: MockScenario) => [...root(scenario), "sports"] as const,
  performance: (scenario: MockScenario) => [...root(scenario), "performance"] as const,

  leagues: {
    all: (scenario: MockScenario) => [...root(scenario), "leagues"] as const,
    list: (scenario: MockScenario, filters?: CatalogFilters) =>
      [...root(scenario), "leagues", "list", normalizeCatalogFilters(filters)] as const,
    detail: (scenario: MockScenario, id: string) =>
      [...root(scenario), "leagues", "detail", id] as const,
  },

  matches: {
    all: (scenario: MockScenario) => [...root(scenario), "matches"] as const,
    list: (scenario: MockScenario, filters?: MatchFilters) =>
      [...root(scenario), "matches", "list", normalizeMatchFilters(filters)] as const,
    detail: (scenario: MockScenario, id: string) =>
      [...root(scenario), "matches", "detail", id] as const,
  },

  picks: {
    all: (scenario: MockScenario) => [...root(scenario), "picks"] as const,
    list: (scenario: MockScenario, filters?: MatchFilters) =>
      [...root(scenario), "picks", "list", normalizeMatchFilters(filters)] as const,
  },

  footballAiPicks: {
    all: (scenario: MockScenario) => [...root(scenario), "football-ai-picks"] as const,
    list: (scenario: MockScenario, filters?: AiPicksFilters) =>
      [...root(scenario), "football-ai-picks", "list", normalizeAiPicksFilters(filters)] as const,
  },

  value: {
    all: (scenario: MockScenario) => [...root(scenario), "value"] as const,
    list: (scenario: MockScenario, filters?: MatchFilters) =>
      [...root(scenario), "value", "list", normalizeMatchFilters(filters)] as const,
  },

  teams: {
    all: (scenario: MockScenario) => [...root(scenario), "teams"] as const,
    list: (scenario: MockScenario, filters?: CatalogFilters) =>
      [...root(scenario), "teams", "list", normalizeCatalogFilters(filters)] as const,
    detail: (scenario: MockScenario, id: string) =>
      [...root(scenario), "teams", "detail", id] as const,
  },

  players: {
    all: (scenario: MockScenario) => [...root(scenario), "players"] as const,
    list: (scenario: MockScenario, filters?: CatalogFilters) =>
      [...root(scenario), "players", "list", normalizeCatalogFilters(filters)] as const,
    detail: (scenario: MockScenario, id: string) =>
      [...root(scenario), "players", "detail", id] as const,
  },

  analyst: {
    all: (scenario: MockScenario) => [...root(scenario), "analyst"] as const,
    session: (scenario: MockScenario, matchId: string, question?: string) =>
      [...root(scenario), "analyst", "session", matchId, question ?? ""] as const,
  },

  footballAiAnalyst: {
    all: (scenario: MockScenario) => [...root(scenario), "football-ai-analyst"] as const,
    detail: (scenario: MockScenario, matchId: string, cutoffAt?: string) =>
      [...root(scenario), "football-ai-analyst", "detail", matchId, cutoffAt ?? ""] as const,
  },

  footballPredictions: {
    all: (scenario: MockScenario) => [...root(scenario), "football-predictions"] as const,
    detail: (scenario: MockScenario, matchId: string, cutoffAt?: string) =>
      [...root(scenario), "football-predictions", "detail", matchId, cutoffAt ?? ""] as const,
  },

  footballValue: {
    all: (scenario: MockScenario) => [...root(scenario), "football-value"] as const,
    detail: (scenario: MockScenario, matchId: string, cutoffAt?: string) =>
      [...root(scenario), "football-value", "detail", matchId, cutoffAt ?? ""] as const,
  },
} as const;
