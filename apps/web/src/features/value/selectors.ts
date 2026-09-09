import type { ValueOpportunity } from "@/types/api";

/**
 * Ordering for the Value Finder.
 *
 * Sorting only reorders opportunities the Value Engine already published; it
 * never derives an edge or an expected value. Rows whose sort key is unavailable
 * are pushed to the end rather than treated as zero, which would rank a missing
 * measurement as if it were a neutral one.
 */

export type ValueSort = "edge" | "expected_value" | "kickoff";

function byNumberDesc(a: number | null, b: number | null): number {
  if (a === null && b === null) return 0;
  if (a === null) return 1;
  if (b === null) return -1;
  return b - a;
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
    case "kickoff":
      return sorted.sort((a, b) => a.match.kickoff_at.localeCompare(b.match.kickoff_at));
  }
}
