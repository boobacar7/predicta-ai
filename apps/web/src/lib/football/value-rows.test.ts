import { lincolnFootballValue } from "@/data/mock/football-engine";
import { footballValueRows, sortFootballValueRows } from "@/lib/football/value-rows";
import { describe, expect, it } from "vitest";

describe("footballValueRows", () => {
  it("copies published Value Engine rows instead of recomputing them", () => {
    const inconsistent = {
      ...lincolnFootballValue,
      value: {
        home: { edge: 0.99, ev: 0.88 },
        draw: { edge: 0.01, ev: 0.02 },
        away: { edge: -0.4, ev: -0.5 },
      },
    };

    const rows = footballValueRows(inconsistent);

    expect(rows[0]?.ev).toBe(0.88);
    expect(rows[0]?.edge).toBe(0.99);
    expect(rows[2]?.ev).toBe(-0.5);
    expect(rows[0]?.implied_probability).toBe(
      inconsistent.market_probabilities.home.implied_probability,
    );
    expect(rows[0]?.model_probability).toBe(inconsistent.prediction.home_probability);
  });

  it("reorders published rows without changing the copied figures", () => {
    const rows = footballValueRows(lincolnFootballValue);
    const byEv = sortFootballValueRows(rows, "ev");

    expect(byEv[0]?.selection).toBe("AWAY");
    expect(byEv.map((row) => row.ev).sort()).toEqual(rows.map((row) => row.ev).sort());
    expect(byEv.find((row) => row.selection === "HOME")?.ev).toBe(lincolnFootballValue.value.home.ev);
  });
});
