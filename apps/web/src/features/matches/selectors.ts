import { isoDaysFromNow } from "@/data/mock/clock";
import type { MatchSummary } from "@/types/api";

/**
 * Presentation selectors for the Match Center.
 *
 * Sport, date, competition and status are filters the endpoint understands and
 * are sent to the data source. Free-text search is applied client side over the
 * returned page, so it stays a display concern until the API exposes a search
 * parameter.
 */

/** Calendar strip dates, as `YYYY-MM-DD`, starting from the current day. */
export function upcomingDays(count: number): string[] {
  return Array.from({ length: count }, (_, offset) => isoDaysFromNow(offset).slice(0, 10));
}

function normalize(value: string): string {
  return value
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "")
    .toLocaleLowerCase("fr-FR");
}

/** Matches whose home or away team name contains the query, accents ignored. */
export function searchMatches(
  matches: readonly MatchSummary[],
  query: string,
): MatchSummary[] {
  const needle = normalize(query.trim());

  if (!needle) {
    return [...matches];
  }

  return matches.filter((match) =>
    [match.home.name, match.home.short_name, match.away.name, match.away.short_name].some(
      (name) => normalize(name).includes(needle),
    ),
  );
}
