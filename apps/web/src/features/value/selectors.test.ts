import { sortValueOpportunities } from "@/features/value/selectors";
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

  it("does not mutate the input array", () => {
    const items = [opportunity("a", { edge_no_vig: 0.01 }), opportunity("b", { edge_no_vig: 0.09 })];
    const order = items.map((item) => item.id);

    sortValueOpportunities(items, "edge");

    expect(items.map((item) => item.id)).toEqual(order);
  });
});
