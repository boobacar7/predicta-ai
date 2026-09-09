"use client";

import { getDataSource } from "@/lib/api";
import { queryKeys } from "@/lib/query/keys";
import type { CatalogFilters, MatchFilters, MockScenario } from "@/types/api";
import { useQuery } from "@tanstack/react-query";

const source = () => getDataSource();

export function useDashboard(scenario: MockScenario) {
  return useQuery({
    queryKey: queryKeys.dashboard(scenario),
    queryFn: () => source().getDashboard(scenario),
  });
}

export function useSports() {
  return useQuery({
    queryKey: queryKeys.sports(),
    queryFn: () => source().getSports(),
  });
}

export function useLeagues(filters?: CatalogFilters) {
  return useQuery({
    queryKey: queryKeys.leagues(filters),
    queryFn: () => source().getLeagues(filters),
  });
}

export function useLeague(id: string) {
  return useQuery({
    queryKey: queryKeys.league(id),
    queryFn: () => source().getLeague(id),
    enabled: Boolean(id),
  });
}

export function useMatches(filters: MatchFilters, scenario: MockScenario) {
  return useQuery({
    queryKey: queryKeys.matches(filters, scenario),
    queryFn: () => source().getMatches(filters, scenario),
  });
}

export function useMatch(id: string, scenario: MockScenario) {
  return useQuery({
    queryKey: queryKeys.match(id, scenario),
    queryFn: () => source().getMatch(id, scenario),
    enabled: Boolean(id),
  });
}

export function usePicks(filters: MatchFilters, scenario: MockScenario) {
  return useQuery({
    queryKey: queryKeys.picks(filters, scenario),
    queryFn: () => source().getPicks(filters, scenario),
  });
}

export function useValueOpportunities(filters: MatchFilters, scenario: MockScenario) {
  return useQuery({
    queryKey: queryKeys.value(filters, scenario),
    queryFn: () => source().getValue(filters, scenario),
  });
}

export function usePerformance(scenario: MockScenario) {
  return useQuery({
    queryKey: queryKeys.performance(scenario),
    queryFn: () => source().getPerformance(scenario),
  });
}

export function useTeams(filters?: CatalogFilters) {
  return useQuery({
    queryKey: queryKeys.teams(filters),
    queryFn: () => source().getTeams(filters),
  });
}

export function useTeam(id: string) {
  return useQuery({
    queryKey: queryKeys.team(id),
    queryFn: () => source().getTeam(id),
    enabled: Boolean(id),
  });
}

export function usePlayers(filters?: CatalogFilters) {
  return useQuery({
    queryKey: queryKeys.players(filters),
    queryFn: () => source().getPlayers(filters),
  });
}

export function usePlayer(id: string) {
  return useQuery({
    queryKey: queryKeys.player(id),
    queryFn: () => source().getPlayer(id),
    enabled: Boolean(id),
  });
}

export function useAnalystSession(matchId: string, question?: string) {
  return useQuery({
    queryKey: queryKeys.analyst(matchId, question),
    queryFn: () => source().getAnalystSession(matchId, question),
    enabled: Boolean(matchId),
  });
}
