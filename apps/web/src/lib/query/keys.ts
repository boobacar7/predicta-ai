import type { CatalogFilters, MatchFilters, MockScenario } from "@/types/api";

export const queryKeys = {
  dashboard: (scenario: MockScenario) => ["dashboard", scenario] as const,
  sports: () => ["sports"] as const,
  leagues: (filters?: CatalogFilters) => ["leagues", filters ?? {}] as const,
  league: (id: string) => ["league", id] as const,
  matches: (filters: MatchFilters, scenario: MockScenario) =>
    ["matches", filters, scenario] as const,
  match: (id: string, scenario: MockScenario) => ["match", id, scenario] as const,
  picks: (filters: MatchFilters, scenario: MockScenario) => ["picks", filters, scenario] as const,
  value: (filters: MatchFilters, scenario: MockScenario) => ["value", filters, scenario] as const,
  performance: (scenario: MockScenario) => ["performance", scenario] as const,
  teams: (filters?: CatalogFilters) => ["teams", filters ?? {}] as const,
  team: (id: string) => ["team", id] as const,
  players: (filters?: CatalogFilters) => ["players", filters ?? {}] as const,
  player: (id: string) => ["player", id] as const,
  analyst: (matchId: string, question?: string) => ["analyst", matchId, question ?? ""] as const,
};
