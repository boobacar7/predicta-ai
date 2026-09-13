import type { MatchSummary } from "@/types/api";

/**
 * Presentation selectors for the Match Center.
 *
 * Sport, date, competition and status are filters the endpoint understands and
 * are sent to the data source. Free-text search is applied client side over the
 * returned page, so it stays a display concern until the API exposes a search
 * parameter.
 *
 * Calendar dates use the wall clock (injectable for tests). Feature views must
 * not import the mock fixture clock.
 */

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

export function toIsoDate(date: Date): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`;
}

/** Calendar strip dates, as `YYYY-MM-DD`, starting from local today unless `from` is given. */
export function upcomingDays(count: number, from: Date = new Date()): string[] {
  const start = new Date(from.getFullYear(), from.getMonth(), from.getDate());

  return Array.from({ length: count }, (_, offset) => {
    const day = new Date(start);
    day.setDate(start.getDate() + offset);
    return toIsoDate(day);
  });
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
