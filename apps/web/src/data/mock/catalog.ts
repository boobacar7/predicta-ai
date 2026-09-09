import type { League, Player, Sport, Team } from "@/types/api";

export const sports: Sport[] = [
  { id: "sport_football", code: "football", name: "Football" },
  { id: "sport_basketball", code: "basketball", name: "Basketball" },
  { id: "sport_tennis", code: "tennis", name: "Tennis" },
];

export const leagues: League[] = [
  {
    id: "lg_continental",
    name: "Continental Premier",
    sport: "football",
    country: "Europe (fictif)",
    season: "2026-27",
    tier: 1,
  },
  {
    id: "lg_northern",
    name: "Northern Championship",
    sport: "football",
    country: "Nord (fictif)",
    season: "2026-27",
    tier: 2,
  },
  {
    id: "lg_metro",
    name: "Metro Basketball League",
    sport: "basketball",
    country: "Atlantique (fictif)",
    season: "2026",
    tier: 1,
  },
  {
    id: "lg_grand_court",
    name: "Grand Court Tour",
    sport: "tennis",
    country: "International (fictif)",
    season: "2026",
    tier: 1,
  },
];

export const teams: Team[] = [
  team("tm_northgate", "Northgate FC", "Northgate", "NGF", "football", "lg_continental"),
  team("tm_harbor", "Harbor Athletic", "Harbor", "HAR", "football", "lg_continental"),
  team("tm_riverside", "Riverside United", "Riverside", "RSU", "football", "lg_continental"),
  team("tm_oakmont", "Oakmont City", "Oakmont", "OAK", "football", "lg_continental"),
  team("tm_silverpark", "Silverpark", "Silverpark", "SLV", "football", "lg_continental"),
  team("tm_westbridge", "Westbridge", "Westbridge", "WBR", "football", "lg_continental"),
  team("tm_calder", "Calder Rovers", "Calder", "CAL", "football", "lg_northern"),
  team("tm_eastmere", "Eastmere", "Eastmere", "EST", "football", "lg_northern"),
  team("tm_helix", "Helix City", "Helix", "HLX", "basketball", "lg_metro"),
  team("tm_meridian", "Meridian", "Meridian", "MRD", "basketball", "lg_metro"),
  team("tm_voss", "Lena Voss", "Voss", "VOS", "tennis", "lg_grand_court"),
  team("tm_elian", "Marco Elian", "Elian", "ELI", "tennis", "lg_grand_court"),
];

export const players: Player[] = [
  {
    id: "pl_voss",
    name: "Lena Voss",
    sport: "tennis",
    team_id: null,
    position: "Droitier, fond de court",
    country: "SVE (fictif)",
  },
  {
    id: "pl_elian",
    name: "Marco Elian",
    sport: "tennis",
    team_id: null,
    position: "Gaucher, service-volée",
    country: "ITA (fictif)",
  },
  {
    id: "pl_kade",
    name: "Jonas Kade",
    sport: "football",
    team_id: "tm_northgate",
    position: "Milieu",
    country: "NED (fictif)",
  },
  {
    id: "pl_orla",
    name: "Orla Simms",
    sport: "football",
    team_id: "tm_harbor",
    position: "Attaquant",
    country: "IRL (fictif)",
  },
  {
    id: "pl_nara",
    name: "Nara Ellison",
    sport: "basketball",
    team_id: "tm_helix",
    position: "Meneur",
    country: "USA (fictif)",
  },
];

export function getLeague(id: string): League {
  const league = leagues.find((item) => item.id === id);
  if (!league) throw new Error(`Unknown mock league: ${id}`);
  return league;
}

export function getTeam(id: string): Team {
  const found = teams.find((item) => item.id === id);
  if (!found) throw new Error(`Unknown mock team: ${id}`);
  return found;
}

function team(
  id: string,
  name: string,
  shortName: string,
  abbreviation: string,
  sport: Team["sport"],
  leagueId: string,
): Team {
  return {
    id,
    name,
    short_name: shortName,
    abbreviation,
    sport,
    league_id: leagueId,
  };
}
