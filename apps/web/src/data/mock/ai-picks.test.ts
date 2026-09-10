import { aiPickExclusions, aiPicks, aiPicksMetadata } from "@/data/mock/ai-picks";
import { describe, expect, it } from "vitest";

/**
 * The fixtures stand in for a real engine response, so numbers that the engine
 * derives must actually be derivable. A fixture that violates one of these
 * identities would let the UI look correct while displaying a combination
 * `ai-picks-0.1` could never produce.
 */

const TOLERANCE = 5e-4;

describe("AI Picks fixtures", () => {
  it("derives the implied probability from the odds", () => {
    for (const pick of aiPicks) {
      expect(pick.implied_probability).toBeCloseTo(1 / pick.odds, 3);
    }
  });

  it("derives the edge from the model and implied probabilities", () => {
    for (const pick of aiPicks) {
      const expected = pick.model_probability - pick.implied_probability;
      expect(Math.abs(pick.edge - expected)).toBeLessThan(TOLERANCE);
    }
  });

  it("derives the expected value from the model probability and the odds", () => {
    for (const pick of aiPicks) {
      const expected = pick.model_probability * pick.odds - 1;
      expect(Math.abs(pick.ev - expected)).toBeLessThan(TOLERANCE);
    }
  });

  it("scores exactly EV plus edge, as the published formula states", () => {
    expect(aiPicksMetadata.scoring_formula).toBe("opportunity_score = EV + Edge");

    for (const pick of aiPicks) {
      expect(Math.abs(pick.opportunity_score - (pick.ev + pick.edge))).toBeLessThan(TOLERANCE);
    }
  });

  it("ranks by descending score, without gaps or ties", () => {
    const ranks = aiPicks.map((pick) => pick.rank);
    expect(ranks).toEqual([...ranks].sort((a, b) => a - b));
    expect(new Set(ranks).size).toBe(ranks.length);

    for (let index = 1; index < aiPicks.length; index += 1) {
      expect(aiPicks[index - 1].opportunity_score).toBeGreaterThanOrEqual(
        aiPicks[index].opportunity_score,
      );
    }
  });

  it("keeps every pick on the candidate model and in mock data mode", () => {
    for (const pick of aiPicks) {
      expect(pick.model_status).toBe("candidate");
      expect(pick.data_mode).toBe("mock");
      expect(pick.status).toBe("eligible");
    }
  });

  it("names a mock odds provider rather than a real bookmaker", () => {
    for (const pick of aiPicks) {
      expect(pick.odds_source).toContain("mock");
    }
  });

  it("explains every exclusion with a reason and a detail", () => {
    expect(aiPickExclusions.length).toBeGreaterThan(0);

    for (const exclusion of aiPickExclusions) {
      expect(exclusion.status).toBe("excluded");
      expect(exclusion.reason).toBeTruthy();
      expect(exclusion.detail.length).toBeGreaterThan(0);
    }
  });
});
