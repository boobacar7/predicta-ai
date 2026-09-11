import { lincolnFootballValue } from "@/data/mock/football-engine";
import { footballValueRows, sortFootballValueRows } from "@/features/value/selectors";
import { describe, expect, it } from "vitest";

describe("footballValueRows", () => {
  it("copies published HOME, DRAW and AWAY figures without changing them", () => {
    const rows = footballValueRows(lincolnFootballValue);

    expect(rows.map((row) => row.selection)).toEqual(["HOME", "DRAW", "AWAY"]);
    expect(rows[0]).toMatchObject({
      model_probability: lincolnFootballValue.prediction.home_probability,
      odds: lincolnFootballValue.odds.home_odds,
      implied_probability: lincolnFootballValue.market_probabilities.home.implied_probability,
      edge: lincolnFootballValue.value.home.edge,
      ev: lincolnFootballValue.value.home.ev,
    });
    expect(rows[2]?.ev).toBe(lincolnFootballValue.value.away.ev);
  });
});

describe("sortFootballValueRows", () => {
  const rows = footballValueRows(lincolnFootballValue);

  it("orders by published edge, strongest first", () => {
    expect(sortFootballValueRows(rows, "edge").map((row) => row.selection)).toEqual([
      "AWAY",
      "DRAW",
      "HOME",
    ]);
  });

  it("orders by published EV, strongest first", () => {
    expect(sortFootballValueRows(rows, "ev").map((row) => row.selection)).toEqual([
      "AWAY",
      "DRAW",
      "HOME",
    ]);
  });

  it("keeps HOME / DRAW / AWAY when sort is selection", () => {
    expect(sortFootballValueRows(rows, "selection").map((row) => row.selection)).toEqual([
      "HOME",
      "DRAW",
      "AWAY",
    ]);
  });

  it("does not mutate the input array", () => {
    const order = rows.map((row) => row.selection);
    sortFootballValueRows(rows, "edge");
    expect(rows.map((row) => row.selection)).toEqual(order);
  });
});
