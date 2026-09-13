import {
  INTER_UDINESE_MATCH_ID,
  TORINO_ROMA_MATCH_ID,
  UDINESE_LAZIO_MATCH_ID,
  interUdineseFootballPrediction,
  torinoRomaFootballPrediction,
  udineseLazioFootballPrediction,
} from "@/data/mock/football-engine";
import type { League, MatchDetail, MatchSummary, MatchStatus, Team } from "@/types/api";

/**
 * SQL-catalog-shaped football matches: identity only.
 *
 * Mirrors `apps/api/app/repositories/sql_mapping.py`: odds, stats, timeline
 * and catalogue predictions stay unpublished. Engine probabilities are loaded
 * separately from `GET /football/predictions/{match_id}`.
 */

const SERIE_A: League = {
  id: "lg_serie_a",
  name: "Serie A",
  sport: "football",
  country: "Italy",
  season: "2026-27",
  tier: 1,
};

const CATALOG_UNAVAILABLE = [
  { field: "odds", reason: "Odds are not published on the catalog read path." },
  { field: "prediction", reason: "Predictions are not published on the catalog read path." },
  { field: "stats", reason: "Match statistics are not published in the catalog store." },
  { field: "timeline", reason: "Match events are not published in the catalog store." },
  { field: "form", reason: "Team form is not published in the catalog store." },
] as const;

const unpublishedScore = {
  home: null,
  away: null,
  quality: {
    availability: "unavailable" as const,
    source: null,
    observed_at: null,
    freshness: null,
    note: "Score is not published for this match yet.",
  },
};

function team(id: string, name: string, abbreviation: string): Team {
  return {
    id,
    name,
    short_name: name,
    sport: "football",
    league_id: SERIE_A.id,
    abbreviation,
  };
}

function catalogMatch(input: {
  id: string;
  home: Team;
  away: Team;
  kickoff_at: string;
  status?: MatchStatus;
}): MatchDetail {
  return {
    id: input.id,
    sport: "football",
    league: SERIE_A,
    home: input.home,
    away: input.away,
    kickoff_at: input.kickoff_at,
    status: input.status ?? "scheduled",
    venue: null,
    score: unpublishedScore,
    prediction_preview: null,
    value_preview: null,
    quality: {
      availability: "available",
      source: "sportmonks",
      observed_at: null,
      freshness: null,
      note: "Catalog identity from the live store. Odds, stats and predictions are not inferred.",
    },
    timeline: [],
    stats: [],
    odds: null,
    prediction: null,
    form: [],
    unavailable_fields: [...CATALOG_UNAVAILABLE],
  };
}

export const engineCatalogMatches: MatchDetail[] = [
  catalogMatch({
    id: TORINO_ROMA_MATCH_ID,
    home: team("tm_torino", "Torino", "TOR"),
    away: team("tm_roma", "Roma", "ROM"),
    kickoff_at: torinoRomaFootballPrediction.cutoff_at,
  }),
  catalogMatch({
    id: INTER_UDINESE_MATCH_ID,
    home: team("tm_inter", "Inter", "INT"),
    away: team("tm_udinese", "Udinese", "UDI"),
    kickoff_at: interUdineseFootballPrediction.cutoff_at,
  }),
  catalogMatch({
    id: UDINESE_LAZIO_MATCH_ID,
    home: team("tm_udinese", "Udinese", "UDI"),
    away: team("tm_lazio", "Lazio", "LAZ"),
    kickoff_at: udineseLazioFootballPrediction.cutoff_at,
  }),
];

export const engineCatalogSummaries: MatchSummary[] = engineCatalogMatches.map((match) => ({
  id: match.id,
  sport: match.sport,
  league: match.league,
  home: match.home,
  away: match.away,
  kickoff_at: match.kickoff_at,
  status: match.status,
  venue: match.venue,
  score: match.score,
  prediction_preview: null,
  value_preview: null,
  quality: match.quality,
}));

export function getEngineCatalogMatch(matchId: string): MatchDetail | undefined {
  return engineCatalogMatches.find((item) => item.id === matchId);
}

export function withMatchStatus(match: MatchSummary, status: MatchStatus): MatchSummary {
  return { ...match, status };
}
