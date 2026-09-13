import type { HistoricalMatchIdentity } from "@/types/api";

/**
 * Structural identities for match ids that exist in the point-in-time archive
 * but have no projected `MatchDetail`.
 *
 * Values are copied from the backend fixture that `c31a367` publishes for
 * `GET /matches/mth_football-sportmonks-19719892`. The mock must be able to
 * serve the same shape, or `MatchDetailView` would only be tested against the
 * projected catalogue and the historical branch would stay dark.
 */
export const historicalMatchIdentities: HistoricalMatchIdentity[] = [
  {
    match_id: "mth_football-sportmonks-19719892",
    home_team_id: "tm_football-sportmonks-10068",
    away_team_id: "tm_football-sportmonks-17303",
    home_team: "Lincoln Red Imps",
    away_team: "Inter Club d'Escaldes",
    league: "Champions League",
    kickoff_at: "2026-07-07T16:00:00Z",
    data_mode: "live",
    resource_scope: "structural_identity",
  },
];
