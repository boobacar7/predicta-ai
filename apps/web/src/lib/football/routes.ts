/**
 * Canonical private-beta football surfaces.
 *
 * These are the only product routes the P1 chrome advertises. Legacy prototype
 * paths keep working through redirects so bookmarks do not 404.
 */

export const P1_SPORT = "football" as const;

export const FOOTBALL_PATHS = {
  dashboard: "/football",
  matches: "/football/matches",
  aiPicks: "/football/ai-picks",
  value: "/football/value",
  aiAnalyst: "/football/ai-analyst",
} as const;

export type FootballPath = (typeof FOOTBALL_PATHS)[keyof typeof FOOTBALL_PATHS];

export function footballMatchPath(matchId: string): string {
  return `${FOOTBALL_PATHS.matches}/${encodeURIComponent(matchId)}`;
}

export function footballAnalystPath(matchId?: string | null): string {
  if (!matchId) return FOOTBALL_PATHS.aiAnalyst;
  return `${FOOTBALL_PATHS.aiAnalyst}?match_id=${encodeURIComponent(matchId)}`;
}

export function footballValuePath(matchId?: string | null): string {
  if (!matchId) return FOOTBALL_PATHS.value;
  return `${FOOTBALL_PATHS.value}?match_id=${encodeURIComponent(matchId)}`;
}

/** Sidebar / bottom-nav active state: `/football` must not match `/football/matches`. */
export function isFootballNavActive(pathname: string, href: string): boolean {
  if (href === FOOTBALL_PATHS.dashboard) {
    return pathname === FOOTBALL_PATHS.dashboard;
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

export const LEGACY_FOOTBALL_REDIRECTS: ReadonlyArray<{
  source: string;
  destination: string;
  permanent: boolean;
}> = [
  { source: "/", destination: FOOTBALL_PATHS.dashboard, permanent: false },
  { source: "/matches", destination: FOOTBALL_PATHS.matches, permanent: true },
  { source: "/matches/:id", destination: `${FOOTBALL_PATHS.matches}/:id`, permanent: true },
  { source: "/picks", destination: FOOTBALL_PATHS.aiPicks, permanent: true },
  { source: "/ai-picks", destination: FOOTBALL_PATHS.aiPicks, permanent: true },
  { source: "/value", destination: FOOTBALL_PATHS.value, permanent: true },
  { source: "/value-finder", destination: FOOTBALL_PATHS.value, permanent: true },
  { source: "/analyst", destination: FOOTBALL_PATHS.aiAnalyst, permanent: true },
  { source: "/ai-analyst", destination: FOOTBALL_PATHS.aiAnalyst, permanent: true },
];
