import { createAnalystSession } from "@/data/mock/analyst";
import { leagues, players, sports, teams } from "@/data/mock/catalog";
import { MOCK_NOW_ISO } from "@/data/mock/clock";
import { matches, matchSummaries } from "@/data/mock/matches";
import { insights, performanceReport } from "@/data/mock/performance";
import {
  applyMatchDetailScenario,
  applyMatchListScenario,
  applyValueScenario,
  isEmptyScenario,
} from "@/data/mock/scenarios";
import { picks, valueOpportunities } from "@/data/mock/signals";
import { DataSourceError } from "@/lib/api/errors";
import type {
  CatalogFilters,
  Envelope,
  LeagueDetail,
  MatchFilters,
  MockScenario,
  PlayerDetail,
  StandingRow,
  TeamDetail,
} from "@/types/api";
import type { DataSource, ListResult } from "@/types/datasource";

/** Simulated provider latency, so loading states are observable in development. */
const DEFAULT_LATENCY_MS = 280;

export interface MockDataSourceOptions {
  /** Which documented fixture scenario this instance serves. */
  scenario?: MockScenario;
  /** Set to 0 in tests to keep them fast and deterministic. */
  latencyMs?: number;
}

/**
 * Serves the versioned fixtures in `src/data/mock`.
 *
 * The scenario is bound once per instance so that `DataSource` keeps the exact
 * shape of the future HTTP contract. Fixtures are fictional and every envelope
 * carries `data_mode: "mock"`.
 */
export class MockDataSource implements DataSource {
  readonly kind = "mock" as const;

  private readonly scenario: MockScenario;
  private readonly latencyMs: number;

  constructor({ scenario = "success", latencyMs = DEFAULT_LATENCY_MS }: MockDataSourceOptions = {}) {
    this.scenario = scenario;
    this.latencyMs = latencyMs;
  }

  async getDashboard() {
    await this.begin();

    const todayMatches = applyMatchListScenario(matchSummaries, this.scenario).filter((item) =>
      item.kickoff_at.startsWith(MOCK_NOW_ISO.slice(0, 10)),
    );

    return envelope({
      headline: "Journée mock du 9 septembre 2026",
      sports,
      matches_today: todayMatches,
      picks: isEmptyScenario(this.scenario) ? [] : picks,
      value_opportunities: isEmptyScenario(this.scenario) ? [] : valueOpportunities,
      insights,
      model_health: performanceReport.summary,
    });
  }

  async getSports() {
    await this.begin();
    return envelope(sports);
  }

  async getLeagues(filters: CatalogFilters = {}) {
    await this.begin();
    const items = leagues.filter((league) => matchesSport(league.sport, filters.sport));
    return envelope(list(items));
  }

  async getLeague(id: string) {
    await this.begin();

    const league = leagues.find((item) => item.id === id);
    if (!league) throw notFound("Ligue");

    const leagueTeams = teams.filter((team) => team.league_id === id);
    const standing: StandingRow[] = leagueTeams.map((team, index) => ({
      rank: index + 1,
      team,
      played: 6,
      points: 15 - index * 2,
      goal_diff: 8 - index * 3,
      quality: {
        availability: "available",
        source: "mock.fixtures.v1",
        observed_at: MOCK_NOW_ISO,
        freshness: "fresh",
        note: "Classement fictif, non issu d'une compétition réelle.",
      },
    }));

    const data: LeagueDetail = {
      league,
      standing,
      recent_matches: matchSummaries.filter((item) => item.league.id === id).slice(0, 4),
      unavailable_fields:
        league.sport === "tennis"
          ? [{ field: "standing", reason: "Pas de classement d'équipe pour le tennis." }]
          : [],
    };

    return envelope(data);
  }

  async getMatches(filters: MatchFilters = {}) {
    await this.begin();

    const items = applyMatchListScenario(matchSummaries, this.scenario).filter((match) => {
      if (!matchesSport(match.sport, filters.sport)) return false;
      if (filters.league_id && filters.league_id !== "all" && match.league.id !== filters.league_id) {
        return false;
      }
      if (filters.status && filters.status !== "all" && match.status !== filters.status) return false;
      if (filters.date && !match.kickoff_at.startsWith(filters.date)) return false;
      return true;
    });

    return envelope(list(items));
  }

  async getMatch(id: string) {
    await this.begin();

    const match = matches.find((item) => item.id === id);
    if (!match) throw notFound("Match");

    return envelope(applyMatchDetailScenario(match, this.scenario));
  }

  async getPicks(filters: MatchFilters = {}) {
    await this.begin();

    const items = (isEmptyScenario(this.scenario) ? [] : picks).filter((pick) =>
      matchesSport(pick.match.sport, filters.sport),
    );

    return envelope(list(items));
  }

  async getValue(filters: MatchFilters = {}) {
    await this.begin();

    const items = applyValueScenario(valueOpportunities, this.scenario).filter((item) =>
      matchesSport(item.match.sport, filters.sport),
    );

    return envelope(list(items));
  }

  async getPerformance() {
    await this.begin();
    return envelope(performanceReport);
  }

  async getTeams(filters: CatalogFilters = {}) {
    await this.begin();

    const items = teams.filter(
      (team) => matchesSport(team.sport, filters.sport) && matchesQuery(team.name, filters.query),
    );

    return envelope(list(items));
  }

  async getTeam(id: string) {
    await this.begin();

    const team = teams.find((item) => item.id === id);
    if (!team) throw notFound("Équipe");

    const league = leagues.find((item) => item.id === team.league_id);
    if (!league) throw notFound("Ligue liée");

    const data: TeamDetail = {
      team,
      league,
      recent_matches: matchSummaries.filter(
        (item) => item.home.id === id || item.away.id === id,
      ),
      stats: [
        {
          key: "elo",
          label: "Elo mock",
          value: 1512,
          unit: "rating",
          quality: {
            availability: "available",
            source: "mock.fixtures.v1",
            observed_at: MOCK_NOW_ISO,
            freshness: "fresh",
            note: "Rating fictif.",
          },
        },
        {
          key: "injuries",
          label: "Blessures",
          value: null,
          unit: null,
          quality: {
            availability: "unavailable",
            source: null,
            observed_at: null,
            freshness: null,
            note: "Les blessures ne sont pas dans le prototype mock.",
          },
        },
      ],
      unavailable_fields: [
        { field: "injuries", reason: "Les blessures ne sont jamais inventées." },
      ],
    };

    return envelope(data);
  }

  async getPlayers(filters: CatalogFilters = {}) {
    await this.begin();

    const items = players.filter(
      (player) =>
        matchesSport(player.sport, filters.sport) && matchesQuery(player.name, filters.query),
    );

    return envelope(list(items));
  }

  async getPlayer(id: string) {
    await this.begin();

    const player = players.find((item) => item.id === id);
    if (!player) throw notFound("Joueur");

    const team = player.team_id ? teams.find((item) => item.id === player.team_id) ?? null : null;
    const hasMinutes = player.sport === "football";

    const data: PlayerDetail = {
      player,
      team,
      stats: [
        {
          key: "minutes",
          label: "Minutes mock",
          value: hasMinutes ? 412 : null,
          unit: "min",
          quality: {
            availability: hasMinutes ? "available" : "unavailable",
            source: hasMinutes ? "mock.fixtures.v1" : null,
            observed_at: hasMinutes ? MOCK_NOW_ISO : null,
            freshness: hasMinutes ? "fresh" : null,
            note: hasMinutes ? "Volume fictif." : "Non applicable dans ce sport mock.",
          },
        },
      ],
      recent_mentions: [],
      unavailable_fields: [
        { field: "availability", reason: "Disponibilité réelle non fournie." },
      ],
    };

    return envelope(data);
  }

  async getAnalystSession(matchId: string, question?: string) {
    await this.begin();

    const match = matches.find((item) => item.id === matchId);
    if (!match) throw notFound("Match");

    return envelope(createAnalystSession(matchId, question));
  }

  /** Applies simulated latency, then fails when the error scenario is active. */
  private async begin(): Promise<void> {
    if (this.latencyMs > 0) {
      await new Promise((resolve) => setTimeout(resolve, this.latencyMs));
    }

    if (this.scenario === "error") {
      throw new DataSourceError({ kind: "mock_scenario" });
    }
  }
}

function notFound(entity: string): DataSourceError {
  return new DataSourceError({
    kind: "not_found",
    message: `${entity} introuvable dans les fixtures mock.`,
  });
}

function list<T>(items: T[]): ListResult<T> {
  return { items, total: items.length };
}

function envelope<T>(data: T): Envelope<T> {
  return {
    data_mode: "mock",
    generated_at: MOCK_NOW_ISO,
    request_id: "req_mock_ui_prototype",
    data,
  };
}

function matchesSport(sport: string, filter?: CatalogFilters["sport"] | MatchFilters["sport"]) {
  return !filter || filter === "all" || filter === sport;
}

function matchesQuery(name: string, query?: string) {
  const needle = query?.trim().toLocaleLowerCase("fr-FR") ?? "";
  return !needle || name.toLocaleLowerCase("fr-FR").includes(needle);
}
