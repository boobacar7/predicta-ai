import { leagues, players, sports, teams } from "@/data/mock/catalog";
import { MOCK_NOW_ISO } from "@/data/mock/clock";
import { createAnalystSession } from "@/data/mock/analyst";
import { matches, matchSummaries } from "@/data/mock/matches";
import { insights, performanceReport } from "@/data/mock/performance";
import { picks, valueOpportunities } from "@/data/mock/signals";
import { getDataSourceMode } from "@/lib/config";
import type {
  CatalogFilters,
  Envelope,
  LeagueDetail,
  MatchDetail,
  MatchFilters,
  MockScenario,
  PlayerDetail,
  StandingRow,
  TeamDetail,
} from "@/types/api";
import type { DataSource, ListResult } from "@/types/datasource";

const LATENCY_MS = 280;

export class MockDataSourceError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "MockDataSourceError";
  }
}

export class MockDataSource implements DataSource {
  readonly mode = "mock" as const;

  async getDashboard(scenario: MockScenario = "success") {
    this.assertScenario(scenario);
    await delay();
    return envelope({
      headline: "Journée mock du 9 septembre 2026",
      sports,
      matches_today: applyMatchScenario(matchSummaries, scenario).filter((item) =>
        item.kickoff_at.startsWith("2026-09-09"),
      ),
      picks: scenario === "empty" ? [] : picks,
      value_opportunities: scenario === "empty" ? [] : valueOpportunities,
      insights,
      model_health: performanceReport.summary,
    });
  }

  async getSports() {
    await delay();
    return envelope(sports);
  }

  async getLeagues(filters: CatalogFilters = {}) {
    await delay();
    const items = leagues.filter((league) => matchesSport(league.sport, filters.sport));
    return envelope({ items, total: items.length });
  }

  async getLeague(id: string) {
    await delay();
    const league = leagues.find((item) => item.id === id);
    if (!league) throw new MockDataSourceError("Ligue introuvable dans les fixtures mock.");

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

  async getMatches(filters: MatchFilters = {}, scenario: MockScenario = "success") {
    this.assertScenario(scenario);
    await delay();
    const items = applyMatchScenario(matchSummaries, scenario).filter((match) => {
      if (!matchesSport(match.sport, filters.sport)) return false;
      if (filters.league_id && filters.league_id !== "all" && match.league.id !== filters.league_id) {
        return false;
      }
      if (filters.status && filters.status !== "all" && match.status !== filters.status) return false;
      if (filters.date && !match.kickoff_at.startsWith(filters.date)) return false;
      return true;
    });
    return envelope({ items, total: items.length });
  }

  async getMatch(id: string, scenario: MockScenario = "success") {
    this.assertScenario(scenario);
    await delay();
    const match = matches.find((item) => item.id === id);
    if (!match) throw new MockDataSourceError("Match introuvable dans les fixtures mock.");
    return envelope(applyMatchDetailScenario(match, scenario));
  }

  async getPicks(filters: MatchFilters = {}, scenario: MockScenario = "success") {
    this.assertScenario(scenario);
    await delay();
    const items = (scenario === "empty" ? [] : picks).filter((pick) =>
      matchesSport(pick.match.sport, filters.sport),
    );
    return envelope({ items, total: items.length });
  }

  async getValue(filters: MatchFilters = {}, scenario: MockScenario = "success") {
    this.assertScenario(scenario);
    await delay();
    let items = scenario === "empty" ? [] : valueOpportunities;
    if (scenario === "stale") {
      items = items.map((item) => ({
        ...item,
        quality: { ...item.quality, availability: "stale", freshness: "stale" as const },
      }));
    }
    items = items.filter((item) => matchesSport(item.match.sport, filters.sport));
    return envelope({ items, total: items.length });
  }

  async getPerformance(scenario: MockScenario = "success") {
    this.assertScenario(scenario);
    await delay();
    return envelope(performanceReport);
  }

  async getTeams(filters: CatalogFilters = {}) {
    await delay();
    const query = filters.query?.trim().toLocaleLowerCase("fr-FR") ?? "";
    const items = teams.filter((team) => {
      if (!matchesSport(team.sport, filters.sport)) return false;
      if (query && !team.name.toLocaleLowerCase("fr-FR").includes(query)) return false;
      return true;
    });
    return envelope({ items, total: items.length });
  }

  async getTeam(id: string) {
    await delay();
    const team = teams.find((item) => item.id === id);
    if (!team) throw new MockDataSourceError("Équipe introuvable dans les fixtures mock.");
    const league = leagues.find((item) => item.id === team.league_id);
    if (!league) throw new MockDataSourceError("Ligue liée introuvable.");

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
    await delay();
    const query = filters.query?.trim().toLocaleLowerCase("fr-FR") ?? "";
    const items = players.filter((player) => {
      if (!matchesSport(player.sport, filters.sport)) return false;
      if (query && !player.name.toLocaleLowerCase("fr-FR").includes(query)) return false;
      return true;
    });
    return envelope({ items, total: items.length });
  }

  async getPlayer(id: string) {
    await delay();
    const player = players.find((item) => item.id === id);
    if (!player) throw new MockDataSourceError("Joueur introuvable dans les fixtures mock.");
    const team = player.team_id ? teams.find((item) => item.id === player.team_id) ?? null : null;

    const data: PlayerDetail = {
      player,
      team,
      stats: [
        {
          key: "minutes",
          label: "Minutes mock",
          value: player.sport === "football" ? 412 : null,
          unit: "min",
          quality: {
            availability: player.sport === "football" ? "available" : "unavailable",
            source: player.sport === "football" ? "mock.fixtures.v1" : null,
            observed_at: player.sport === "football" ? MOCK_NOW_ISO : null,
            freshness: player.sport === "football" ? "fresh" : null,
            note: player.sport === "football" ? "Volume fictif." : "Non applicable dans ce sport mock.",
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
    await delay();
    const match = matches.find((item) => item.id === matchId);
    if (!match) throw new MockDataSourceError("Match introuvable pour l'analyste mock.");
    return envelope(createAnalystSession(matchId, question));
  }

  private assertScenario(scenario: MockScenario) {
    if (scenario === "error") {
      throw new MockDataSourceError(
        "Scénario mock « error » : le provider fictif a renvoyé une erreur volontaire.",
      );
    }
  }
}

export function createHttpDataSource(): DataSource {
  return {
    mode: "http",
    getDashboard: notImplemented("getDashboard"),
    getSports: notImplemented("getSports"),
    getLeagues: notImplemented("getLeagues"),
    getLeague: notImplemented("getLeague"),
    getMatches: notImplemented("getMatches"),
    getMatch: notImplemented("getMatch"),
    getPicks: notImplemented("getPicks"),
    getValue: notImplemented("getValue"),
    getPerformance: notImplemented("getPerformance"),
    getTeams: notImplemented("getTeams"),
    getTeam: notImplemented("getTeam"),
    getPlayers: notImplemented("getPlayers"),
    getPlayer: notImplemented("getPlayer"),
    getAnalystSession: notImplemented("getAnalystSession"),
  };
}

export function createDataSource(): DataSource {
  return getDataSourceMode() === "http" ? createHttpDataSource() : new MockDataSource();
}

function notImplemented(method: string) {
  return async () => {
    throw new Error(
      `HttpDataSource.${method} n'est pas implémenté. Agent Frontend : brancher le client OpenAPI ici.`,
    );
  };
}

function envelope<T>(data: T): Envelope<T> {
  return {
    data_mode: "mock",
    generated_at: MOCK_NOW_ISO,
    request_id: "req_mock_ui_prototype",
    data,
  };
}

function delay() {
  return new Promise((resolve) => setTimeout(resolve, LATENCY_MS));
}

function matchesSport(sport: string, filter?: CatalogFilters["sport"] | MatchFilters["sport"]) {
  return !filter || filter === "all" || filter === sport;
}

function applyMatchScenario(items: typeof matchSummaries, scenario: MockScenario) {
  if (scenario === "empty") return [];
  if (scenario === "partial") {
    return items.map((item) =>
      item.id === "mth_riverside_oakmont"
        ? item
        : {
            ...item,
            prediction_preview: item.prediction_preview
              ? { ...item.prediction_preview, quality: { ...item.prediction_preview.quality, availability: "partial" as const } }
              : item.prediction_preview,
          },
    );
  }
  if (scenario === "stale") {
    return items.map((item) => ({
      ...item,
      quality: { ...item.quality, availability: "stale" as const, freshness: "stale" as const },
    }));
  }
  return items;
}

function applyMatchDetailScenario(match: MatchDetail, scenario: MockScenario): MatchDetail {
  if (scenario === "partial") {
    return {
      ...match,
      quality: { ...match.quality, availability: "partial", note: "Scénario mock partiel." },
    };
  }
  if (scenario === "stale") {
    return {
      ...match,
      quality: { ...match.quality, availability: "stale", freshness: "stale" },
    };
  }
  return match;
}

export type { ListResult };
