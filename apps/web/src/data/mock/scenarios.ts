import type {
  MatchDetail,
  MatchSummary,
  MockScenario,
  ValueOpportunity,
} from "@/types/api";

/**
 * Scenario transforms for the mock fixtures.
 *
 * The named scenarios come from docs/development-conventions.md §8 and let every
 * data-driven view be inspected without a backend:
 *
 * - `success` — nominal payload;
 * - `empty`   — a genuine absence of results, distinct from an error;
 * - `partial` — usable payload with some fields flagged unavailable;
 * - `stale`   — payload kept, but freshness degraded;
 * - `error`   — simulated provider failure, raised by the data source itself.
 *
 * Transforms are pure and never mutate the fixtures, so a scenario switch cannot
 * leak into another query.
 */

/** The one match kept intact under `partial`, to exercise mixed-quality lists. */
const PARTIAL_REFERENCE_MATCH_ID = "mth_riverside_oakmont";

export function isEmptyScenario(scenario: MockScenario): boolean {
  return scenario === "empty";
}

export function applyMatchListScenario(
  items: readonly MatchSummary[],
  scenario: MockScenario,
): MatchSummary[] {
  if (isEmptyScenario(scenario)) {
    return [];
  }

  if (scenario === "partial") {
    return items.map((item) =>
      item.id === PARTIAL_REFERENCE_MATCH_ID || !item.prediction_preview
        ? { ...item }
        : {
            ...item,
            prediction_preview: {
              ...item.prediction_preview,
              quality: { ...item.prediction_preview.quality, availability: "partial" },
            },
          },
    );
  }

  if (scenario === "stale") {
    return items.map((item) => ({
      ...item,
      quality: { ...item.quality, availability: "stale", freshness: "stale" },
    }));
  }

  return items.map((item) => ({ ...item }));
}

export function applyMatchDetailScenario(
  match: MatchDetail,
  scenario: MockScenario,
): MatchDetail {
  if (scenario === "partial") {
    return {
      ...match,
      quality: { ...match.quality, availability: "partial", note: "Scénario mock partiel." },
    };
  }

  if (scenario === "stale") {
    return {
      ...match,
      quality: { ...match.quality, availability: "stale", freshness: "stale" },
    };
  }

  return match;
}

export function applyValueScenario(
  items: readonly ValueOpportunity[],
  scenario: MockScenario,
): ValueOpportunity[] {
  if (isEmptyScenario(scenario)) {
    return [];
  }

  if (scenario === "stale") {
    return items.map((item) => ({
      ...item,
      quality: { ...item.quality, availability: "stale", freshness: "stale" },
    }));
  }

  return items.map((item) => ({ ...item }));
}
