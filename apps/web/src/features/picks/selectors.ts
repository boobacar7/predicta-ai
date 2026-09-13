import type { AiPick, AiPickExclusion, AiPickExclusionReason } from "@/types/api";

/**
 * Read-only projections over an AI Picks response.
 *
 * Nothing here derives a probability, an edge, an expected value or a rank:
 * those come from `ai-picks-0.1` and are displayed as published. These helpers
 * only count, average and group values the engine already returned, which is
 * presentation work and belongs outside the components.
 */

export interface AiPicksSummary {
  /** Eligible opportunities across every page, as counted by the engine. */
  readonly total: number;
  /** How many are on the page currently loaded. */
  readonly displayed: number;
  /** Best available opportunity by engine rank, or null when the page is empty. */
  readonly best: AiPick | null;
  /** Mean over the loaded page only, or null when there is nothing to average. */
  readonly averageEv: number | null;
  readonly averageEdge: number | null;
}

function mean(values: readonly number[]): number | null {
  if (values.length === 0) return null;
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

/**
 * Averages cover the loaded page, not the whole result set.
 *
 * The engine publishes no aggregate, and averaging a page while labelling it as
 * a global figure would overstate what is known. The view states the scope.
 */
export function summarizeAiPicks(items: readonly AiPick[], total: number): AiPicksSummary {
  const best = items.reduce<AiPick | null>(
    (current, item) => (current === null || item.rank < current.rank ? item : current),
    null,
  );

  return {
    total,
    displayed: items.length,
    best,
    averageEv: mean(items.map((item) => item.ev)),
    averageEdge: mean(items.map((item) => item.edge)),
  };
}

export interface ExclusionGroup {
  readonly reason: AiPickExclusionReason;
  readonly count: number;
  readonly items: AiPickExclusion[];
}

/** Groups rejections by rule, most frequent first, so a rule that empties the page is obvious. */
export function groupExclusions(exclusions: readonly AiPickExclusion[]): ExclusionGroup[] {
  const groups = new Map<AiPickExclusionReason, AiPickExclusion[]>();

  for (const exclusion of exclusions) {
    const bucket = groups.get(exclusion.reason);
    if (bucket) bucket.push(exclusion);
    else groups.set(exclusion.reason, [exclusion]);
  }

  return [...groups.entries()]
    .map(([reason, items]) => ({ reason, count: items.length, items }))
    .sort((a, b) => b.count - a.count || a.reason.localeCompare(b.reason));
}

export interface PageInfo {
  readonly page: number;
  readonly pageCount: number;
  readonly hasPrevious: boolean;
  readonly hasNext: boolean;
  readonly rangeStart: number;
  readonly rangeEnd: number;
}

/** Derives page navigation from the server's own `total`, `limit` and `offset`. */
export function describePage(total: number, limit: number, offset: number): PageInfo {
  const safeLimit = Math.max(1, limit);
  const pageCount = Math.max(1, Math.ceil(total / safeLimit));
  const page = Math.floor(offset / safeLimit) + 1;

  return {
    page,
    pageCount,
    hasPrevious: offset > 0,
    hasNext: offset + safeLimit < total,
    rangeStart: total === 0 ? 0 : offset + 1,
    rangeEnd: Math.min(offset + safeLimit, total),
  };
}
