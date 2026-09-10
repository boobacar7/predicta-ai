import type { ValueOpportunity } from "@/types/api";

/**
 * Selection, ordering and paging for the Value Finder.
 *
 * Everything here reorders or hides opportunities the Value Engine already
 * published. No edge, expected value, implied probability or no-vig probability
 * is derived in the frontend.
 *
 * Rows whose key is unavailable are never treated as zero: they sort last and
 * are excluded by a numeric threshold, because an unknown edge is not a null
 * edge and must not rank as a neutral one.
 */

export type ValueSort = "edge" | "expected_value" | "probability" | "odds" | "kickoff";

export interface ValueFilters {
  /** Market label, or "all". Compared case-insensitively. */
  readonly market: string;
  /** Minimum published no-vig edge, as a raw ratio. `null` disables the rule. */
  readonly minEdge: number | null;
  readonly minEv: number | null;
  readonly minProbability: number | null;
  readonly minOdds: number | null;
}

export const defaultValueFilters: ValueFilters = {
  market: "all",
  minEdge: null,
  minEv: null,
  minProbability: null,
  minOdds: null,
};

function byNumberDesc(a: number | null, b: number | null): number {
  if (a === null && b === null) return 0;
  if (a === null) return 1;
  if (b === null) return -1;
  return b - a;
}

/** `null` fails every threshold: an unmeasured value cannot be shown to clear a bar. */
function meets(value: number | null, minimum: number | null): boolean {
  if (minimum === null) return true;
  if (value === null) return false;
  return value >= minimum;
}

/** Markets present in the result set, for the filter control. */
export function availableMarkets(items: readonly ValueOpportunity[]): string[] {
  return [...new Set(items.map((item) => item.market))].sort((a, b) => a.localeCompare(b, "fr-FR"));
}

export function filterValueOpportunities(
  items: readonly ValueOpportunity[],
  filters: ValueFilters,
): ValueOpportunity[] {
  return items.filter((item) => {
    if (filters.market !== "all" && item.market.toLowerCase() !== filters.market.toLowerCase()) {
      return false;
    }

    return (
      meets(item.edge_no_vig, filters.minEdge) &&
      meets(item.expected_value, filters.minEv) &&
      meets(item.calibrated_probability, filters.minProbability) &&
      meets(item.decimal_odds, filters.minOdds)
    );
  });
}

export function sortValueOpportunities(
  items: readonly ValueOpportunity[],
  sort: ValueSort,
): ValueOpportunity[] {
  const sorted = [...items];

  switch (sort) {
    case "edge":
      return sorted.sort((a, b) => byNumberDesc(a.edge_no_vig, b.edge_no_vig));
    case "expected_value":
      return sorted.sort((a, b) => byNumberDesc(a.expected_value, b.expected_value));
    case "probability":
      return sorted.sort((a, b) => byNumberDesc(a.calibrated_probability, b.calibrated_probability));
    case "odds":
      return sorted.sort((a, b) => byNumberDesc(a.decimal_odds, b.decimal_odds));
    case "kickoff":
      return sorted.sort((a, b) => a.match.kickoff_at.localeCompare(b.match.kickoff_at));
  }
}

export interface ValuePage {
  readonly items: ValueOpportunity[];
  readonly total: number;
  readonly page: number;
  readonly pageCount: number;
  readonly hasPrevious: boolean;
  readonly hasNext: boolean;
}

/**
 * Client-side paging.
 *
 * `GET /value` paginates server-side, but market and threshold refinements are
 * not part of its parameters, so they run here and paging must follow them.
 * The view says how many opportunities were loaded, so the count is never read
 * as a catalogue-wide total.
 */
export function paginateValueOpportunities(
  items: readonly ValueOpportunity[],
  page: number,
  pageSize: number,
): ValuePage {
  const size = Math.max(1, pageSize);
  const pageCount = Math.max(1, Math.ceil(items.length / size));
  const current = Math.min(Math.max(1, page), pageCount);
  const start = (current - 1) * size;

  return {
    items: items.slice(start, start + size),
    total: items.length,
    page: current,
    pageCount,
    hasPrevious: current > 1,
    hasNext: current < pageCount,
  };
}
