import { formatKickoff } from "@/lib/format/dates";

/**
 * Rendering of match identity published by the AI Picks engine and by
 * `GET /matches/{match_id}`.
 *
 * `home_team` and `away_team` are nullable in the contract: the point-in-time
 * archive resolves a canonical label or it does not. A missing label is a real
 * gap in the data and must read as one. It is never replaced by an id, an
 * abbreviation, or a guess, and the words `null`, `undefined` and `NaN` must
 * never reach the screen.
 */
export const UNKNOWN_IDENTITY_LABEL = "Information indisponible";

export interface MatchupLabel {
  /** True when both canonical labels were published. */
  readonly resolved: boolean;
  readonly home: string;
  readonly away: string;
  /** Single-line form, for headings and card titles. */
  readonly text: string;
}

export function formatMatchup(
  homeTeam: string | null | undefined,
  awayTeam: string | null | undefined,
): MatchupLabel {
  const home = usableLabel(homeTeam);
  const away = usableLabel(awayTeam);
  const resolved = home !== null && away !== null;

  return {
    resolved,
    home: home ?? UNKNOWN_IDENTITY_LABEL,
    away: away ?? UNKNOWN_IDENTITY_LABEL,
    // Always keep the "Home vs Away" shape. A missing side is a labelled gap,
    // not a reason to hide the side that did resolve.
    text: `${home ?? UNKNOWN_IDENTITY_LABEL} vs ${away ?? UNKNOWN_IDENTITY_LABEL}`,
  };
}

/**
 * Formats a kickoff, tolerating absence and unparseable input.
 *
 * The contract declares `kickoff_at` required and non-nullable on `AiPick`, so
 * the fallback is not an expected branch. It exists because a malformed
 * timestamp must degrade to a readable gap rather than render `Invalid Date`.
 */
export function formatKickoffOrUnknown(value: string | null | undefined): string {
  if (typeof value !== "string" || value.trim() === "") {
    return UNKNOWN_IDENTITY_LABEL;
  }

  if (Number.isNaN(Date.parse(value))) {
    return UNKNOWN_IDENTITY_LABEL;
  }

  return formatKickoff(value);
}

function usableLabel(value: string | null | undefined): string | null {
  if (typeof value !== "string") {
    return null;
  }

  const trimmed = value.trim();
  return trimmed === "" ? null : trimmed;
}
