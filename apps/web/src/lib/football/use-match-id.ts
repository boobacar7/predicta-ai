"use client";

import { firstFootballMatchId } from "@/lib/football/match-options";
import { P1_SPORT } from "@/lib/football/routes";
import { useFootballAiPicks, useMatches } from "@/lib/query/hooks";
import { useSearchParams } from "next/navigation";

/**
 * Resolves the football `match_id` for Analyst and Value Finder.
 *
 * URL wins. Otherwise the first published football pick, then the first
 * football catalogue match. Nothing is imported from the mock fixture modules.
 */
export function useFootballMatchId(): {
  matchId: string;
  requested: string;
  pending: boolean;
} {
  const searchParams = useSearchParams();
  const requested = searchParams.get("match_id")?.trim() ?? "";
  const picks = useFootballAiPicks({ limit: 20 });
  const matches = useMatches({ sport: P1_SPORT });

  const matchId = firstFootballMatchId({
    requested,
    picks: picks.data?.data.items,
    matches: matches.data?.data.items,
  });

  const pending = !requested && (picks.isPending || matches.isPending);

  return { matchId, requested, pending };
}
