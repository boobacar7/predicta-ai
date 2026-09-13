import { formatMatchup } from "@/lib/format/identity";
import type { AiPick, MatchSummary } from "@/types/api";

export interface FootballMatchOption {
  id: string;
  label: string;
}

/**
 * Match picker options from live football lists, never from fixture modules.
 *
 * Catalogue matches and AI Picks can disagree on which ids exist. The current
 * `match_id` is always kept so a deep link remains selectable even when that
 * match is absent from the current page of results.
 */
export function footballMatchOptions(args: {
  matches?: readonly MatchSummary[];
  picks?: readonly AiPick[];
  currentId?: string | null;
}): FootballMatchOption[] {
  const byId = new Map<string, string>();

  for (const match of args.matches ?? []) {
    byId.set(match.id, `${match.home.short_name} · ${match.away.short_name}`);
  }

  for (const pick of args.picks ?? []) {
    if (byId.has(pick.match_id)) continue;
    byId.set(pick.match_id, formatMatchup(pick.home_team, pick.away_team).text);
  }

  const currentId = args.currentId?.trim();
  if (currentId && !byId.has(currentId)) {
    byId.set(currentId, currentId);
  }

  return [...byId.entries()].map(([id, label]) => ({ id, label }));
}

export function firstFootballMatchId(args: {
  requested?: string | null;
  picks?: readonly AiPick[];
  matches?: readonly MatchSummary[];
}): string {
  const requested = args.requested?.trim();
  if (requested) return requested;
  const fromPick = args.picks?.[0]?.match_id?.trim();
  if (fromPick) return fromPick;
  const fromMatch = args.matches?.[0]?.id?.trim();
  return fromMatch ?? "";
}
