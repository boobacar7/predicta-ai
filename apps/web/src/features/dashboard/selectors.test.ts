import { selectDashboard, summarizeFreshness } from "@/features/dashboard/selectors";
import type {
  AvailabilityStatus,
  DashboardSnapshot,
  MatchSummary,
  SportCode,
} from "@/types/api";
import { describe, expect, it } from "vitest";

function match(
  id: string,
  sport: SportCode,
  availability: AvailabilityStatus = "available",
): MatchSummary {
  return {
    id,
    sport,
    quality: {
      availability,
      source: "test",
      observed_at: "2026-09-09T18:00:00.000Z",
      freshness: "fresh",
      note: null,
    },
  } as MatchSummary;
}

function snapshot(matches: MatchSummary[]): DashboardSnapshot {
  return {
    headline: "Test",
    sports: [],
    matches_today: matches,
    picks: matches.map((item) => ({ id: `pick_${item.id}`, match: item })),
    value_opportunities: matches.map((item) => ({ id: `val_${item.id}`, match: item })),
    insights: [],
    model_health: {},
  } as unknown as DashboardSnapshot;
}

describe("selectDashboard", () => {
  const matches = [
    match("a", "football"),
    match("b", "basketball"),
    match("c", "football"),
  ];

  it("keeps everything when no sport is selected", () => {
    const view = selectDashboard(snapshot(matches), "all");

    expect(view.matches).toHaveLength(3);
  });

  it("narrows matches, picks and value opportunities consistently", () => {
    const view = selectDashboard(snapshot(matches), "football");

    expect(view.matches.map((item) => item.id)).toEqual(["a", "c"]);
    expect(view.picks).toHaveLength(2);
    expect(view.valueOpportunities).toHaveLength(2);
  });

  it("returns an empty selection rather than falling back to everything", () => {
    const view = selectDashboard(snapshot(matches), "tennis");

    expect(view.matches).toHaveLength(0);
    expect(view.picks).toHaveLength(0);
  });
});

describe("summarizeFreshness", () => {
  it("counts each availability state", () => {
    const summary = summarizeFreshness([
      match("a", "football", "available"),
      match("b", "football", "stale"),
      match("c", "football", "partial"),
      match("d", "football", "unavailable"),
    ]);

    expect(summary.total).toBe(4);
    expect(summary.counts).toEqual({ available: 1, stale: 1, partial: 1, unavailable: 1 });
    expect(summary.degraded).toBe(true);
  });

  it("reports a fully available set as not degraded", () => {
    const summary = summarizeFreshness([match("a", "football"), match("b", "football")]);

    expect(summary.degraded).toBe(false);
  });

  it("handles an empty set without claiming completeness", () => {
    const summary = summarizeFreshness([]);

    expect(summary.total).toBe(0);
    expect(summary.degraded).toBe(false);
  });
});
