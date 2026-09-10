"use client";

import { useMockScenario } from "@/data/mock/scenario-context";
import { getDataSource } from "@/lib/api";
import { queryKeys } from "@/lib/query/keys";
import type { AiPicksFilters, CatalogFilters, MatchFilters } from "@/types/api";
import type { DataSource } from "@/types/datasource";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { useMemo } from "react";

/**
 * Typed read hooks, one per endpoint.
 *
 * The active data source and the mock scenario are resolved here rather than in
 * views, so a component asks for `useMatches({ sport })` and stays unaware of
 * whether the answer came from fixtures or the API.
 */

function useSource(): { source: DataSource; scenario: ReturnType<typeof useMockScenario> } {
  const scenario = useMockScenario();
  return useMemo(() => ({ source: getDataSource(scenario), scenario }), [scenario]);
}

export function useDashboard() {
  const { source, scenario } = useSource();

  return useQuery({
    queryKey: queryKeys.dashboard(scenario),
    queryFn: () => source.getDashboard(),
  });
}

export function useSports() {
  const { source, scenario } = useSource();

  return useQuery({
    queryKey: queryKeys.sports(scenario),
    queryFn: () => source.getSports(),
  });
}

export function useLeagues(filters?: CatalogFilters) {
  const { source, scenario } = useSource();

  return useQuery({
    queryKey: queryKeys.leagues.list(scenario, filters),
    queryFn: () => source.getLeagues(filters),
  });
}

export function useLeague(id: string) {
  const { source, scenario } = useSource();

  return useQuery({
    queryKey: queryKeys.leagues.detail(scenario, id),
    queryFn: () => source.getLeague(id),
    enabled: Boolean(id),
  });
}

export function useMatches(filters?: MatchFilters) {
  const { source, scenario } = useSource();

  return useQuery({
    queryKey: queryKeys.matches.list(scenario, filters),
    queryFn: () => source.getMatches(filters),
  });
}

export function useMatch(id: string) {
  const { source, scenario } = useSource();

  return useQuery({
    queryKey: queryKeys.matches.detail(scenario, id),
    queryFn: () => source.getMatch(id),
    enabled: Boolean(id),
  });
}

export function usePicks(filters?: MatchFilters) {
  const { source, scenario } = useSource();

  return useQuery({
    queryKey: queryKeys.picks.list(scenario, filters),
    queryFn: () => source.getPicks(filters),
  });
}

/**
 * `GET /football/ai-picks`.
 *
 * `placeholderData: keepPreviousData` keeps the current page on screen while the
 * next one loads, so paging or nudging a threshold does not blank the list.
 */
export function useFootballAiPicks(filters?: AiPicksFilters) {
  const { source, scenario } = useSource();

  return useQuery({
    queryKey: queryKeys.footballAiPicks.list(scenario, filters),
    queryFn: () => source.getFootballAiPicks(filters),
    placeholderData: keepPreviousData,
  });
}

export function useValueOpportunities(filters?: MatchFilters) {
  const { source, scenario } = useSource();

  return useQuery({
    queryKey: queryKeys.value.list(scenario, filters),
    queryFn: () => source.getValue(filters),
  });
}

export function usePerformance() {
  const { source, scenario } = useSource();

  return useQuery({
    queryKey: queryKeys.performance(scenario),
    queryFn: () => source.getPerformance(),
  });
}

export function useTeams(filters?: CatalogFilters) {
  const { source, scenario } = useSource();

  return useQuery({
    queryKey: queryKeys.teams.list(scenario, filters),
    queryFn: () => source.getTeams(filters),
  });
}

export function useTeam(id: string) {
  const { source, scenario } = useSource();

  return useQuery({
    queryKey: queryKeys.teams.detail(scenario, id),
    queryFn: () => source.getTeam(id),
    enabled: Boolean(id),
  });
}

export function usePlayers(filters?: CatalogFilters) {
  const { source, scenario } = useSource();

  return useQuery({
    queryKey: queryKeys.players.list(scenario, filters),
    queryFn: () => source.getPlayers(filters),
  });
}

export function usePlayer(id: string) {
  const { source, scenario } = useSource();

  return useQuery({
    queryKey: queryKeys.players.detail(scenario, id),
    queryFn: () => source.getPlayer(id),
    enabled: Boolean(id),
  });
}

export function useAnalystSession(matchId: string, question?: string) {
  const { source, scenario } = useSource();

  return useQuery({
    queryKey: queryKeys.analyst.session(scenario, matchId, question),
    queryFn: () => source.getAnalystSession(matchId, question),
    enabled: Boolean(matchId),
  });
}
