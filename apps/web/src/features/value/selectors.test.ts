import {
  availableMarkets,
  defaultValueFilters,
  filterValueOpportunities,
  paginateValueOpportunities,
  sortValueOpportunities,
} from "@/features/value/selectors";
import type { ValueOpportunity } from "@/types/api";
import { describe, expect, it } from "vitest";

function opportunity(
  id: string,
  overrides: Partial<ValueOpportunity> & { kickoff?: string } = {},
): ValueOpportunity {
  const { kickoff = "2026-09-09T18:00:00.000Z", ...rest } = overrides;

  return {
    id,
    match: { kickoff_at: kickoff } as ValueOpportunity["match"],
    market: "1x2",
    selection: "home",
    selection_label: "Home",
    calibrated_probability: 0.5,
    decimal_odds: 2.2,
    implied_probability_raw: 0.4545,
    no_vig_probability: 0.44,
    overround: 0.05,
    edge_raw: 0.045,
    edge_no_vig: 0.06,
    expected_value: 0.1,
    formula_version: "value-0.1",
    odds_observed_at: "2026-09-09T17:00:00.000Z",
    prediction_cutoff_at: "2026-09-09T16:00:00.000Z",
    quality: {
      availability: "available",
      source: "test",
      observed_at: "2026-09-09T17:00:00.000Z",
      freshness: "fresh",
      note: null,
    },
    ...rest,
  };
}

describe("sortValueOpportunities", () => {
  it("orders by edge, strongest first", () => {
    const items = [
      opportunity("low", { edge_no_vig: 0.01 }),
      opportunity("high", { edge_no_vig: 0.09 }),
      opportunity("mid", { edge_no_vig: 0.05 }),
    ];

    expect(sortValueOpportunities(items, "edge").map((item) => item.id)).toEqual([
      "high",
      "mid",
      "low",
    ]);
  });

  it("orders by expected value, strongest first", () => {
    const items = [
      opportunity("a", { expected_value: 0.02 }),
      opportunity("b", { expected_value: 0.31 }),
    ];

    expect(sortValueOpportunities(items, "expected_value").map((item) => item.id)).toEqual([
      "b",
      "a",
    ]);
  });

  it("orders by kickoff, soonest first", () => {
    const items = [
      opportunity("later", { kickoff: "2026-09-10T12:00:00.000Z" }),
      opportunity("sooner", { kickoff: "2026-09-09T12:00:00.000Z" }),
    ];

    expect(sortValueOpportunities(items, "kickoff").map((item) => item.id)).toEqual([
      "sooner",
      "later",
    ]);
  });

  /**
   * A missing edge is unknown, not neutral. Ranking it as 0 would place it above
   * every genuinely negative edge and imply a measurement that does not exist.
   */
  it("pushes rows with an unavailable sort key to the end", () => {
    const items = [
      opportunity("unknown", { edge_no_vig: null }),
      opportunity("negative", { edge_no_vig: -0.04 }),
      opportunity("positive", { edge_no_vig: 0.04 }),
    ];

    expect(sortValueOpportunities(items, "edge").map((item) => item.id)).toEqual([
      "positive",
      "negative",
      "unknown",
    ]);
  });

  it("orders by model probability, strongest first", () => {
    const items = [
      opportunity("low", { calibrated_probability: 0.31 }),
      opportunity("high", { calibrated_probability: 0.72 }),
    ];

    expect(sortValueOpportunities(items, "probability").map((item) => item.id)).toEqual([
      "high",
      "low",
    ]);
  });

  it("orders by odds, longest first", () => {
    const items = [
      opportunity("short", { decimal_odds: 1.4 }),
      opportunity("long", { decimal_odds: 6.5 }),
    ];

    expect(sortValueOpportunities(items, "odds").map((item) => item.id)).toEqual([
      "long",
      "short",
    ]);
  });

  it("does not mutate the input array", () => {
    const items = [opportunity("a", { edge_no_vig: 0.01 }), opportunity("b", { edge_no_vig: 0.09 })];
    const order = items.map((item) => item.id);

    sortValueOpportunities(items, "edge");

    expect(items.map((item) => item.id)).toEqual(order);
  });
});

describe("filterValueOpportunities", () => {
  it("keeps everything when no rule is active", () => {
    const items = [opportunity("a"), opportunity("b")];

    expect(filterValueOpportunities(items, defaultValueFilters)).toHaveLength(2);
  });

  it("filters by market, ignoring case", () => {
    const items = [opportunity("a", { market: "1x2" }), opportunity("b", { market: "btts" })];

    const kept = filterValueOpportunities(items, { ...defaultValueFilters, market: "1X2" });

    expect(kept.map((item) => item.id)).toEqual(["a"]);
  });

  it("applies the edge, EV, probability and odds thresholds together", () => {
    const items = [
      opportunity("weak", { edge_no_vig: 0.01, expected_value: 0.02 }),
      opportunity("strong", { edge_no_vig: 0.08, expected_value: 0.2 }),
    ];

    const kept = filterValueOpportunities(items, {
      ...defaultValueFilters,
      minEdge: 0.05,
      minEv: 0.1,
    });

    expect(kept.map((item) => item.id)).toEqual(["strong"]);
  });

  it("keeps a value sitting exactly on the threshold", () => {
    const items = [opportunity("exact", { edge_no_vig: 0.05 })];

    expect(filterValueOpportunities(items, { ...defaultValueFilters, minEdge: 0.05 })).toHaveLength(
      1,
    );
  });

  /**
   * The core integrity rule: an unmeasured edge must not be read as zero, so it
   * cannot be shown to clear a threshold it was never evaluated against.
   */
  it("excludes an unavailable value instead of treating it as zero", () => {
    const items = [opportunity("unknown", { edge_no_vig: null })];

    expect(filterValueOpportunities(items, { ...defaultValueFilters, minEdge: 0 })).toEqual([]);
    expect(filterValueOpportunities(items, defaultValueFilters)).toHaveLength(1);
  });
});

describe("availableMarkets", () => {
  it("lists each market once, sorted", () => {
    const items = [
      opportunity("a", { market: "1x2" }),
      opportunity("b", { market: "btts" }),
      opportunity("c", { market: "1x2" }),
    ];

    expect(availableMarkets(items)).toEqual(["1x2", "btts"]);
  });
});

describe("paginateValueOpportunities", () => {
  const items = Array.from({ length: 5 }, (_, index) => opportunity(`item-${index}`));

  it("slices the requested page and reports the refined total", () => {
    const page = paginateValueOpportunities(items, 2, 2);

    expect(page.items.map((item) => item.id)).toEqual(["item-2", "item-3"]);
    expect(page).toMatchObject({ total: 5, page: 2, pageCount: 3, hasPrevious: true, hasNext: true });
  });

  it("clamps a page beyond the end instead of showing nothing", () => {
    const page = paginateValueOpportunities(items, 99, 2);

    expect(page.page).toBe(3);
    expect(page.items).toHaveLength(1);
  });

  it("stays on a single valid page when the list is empty", () => {
    const page = paginateValueOpportunities([], 1, 8);

    expect(page).toMatchObject({ total: 0, page: 1, pageCount: 1, hasNext: false });
  });
});
