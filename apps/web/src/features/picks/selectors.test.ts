import { aiPicks } from "@/data/mock/ai-picks";
import { describePage, groupExclusions, summarizeAiPicks } from "@/features/picks/selectors";
import type { AiPickExclusion } from "@/types/api";
import { describe, expect, it } from "vitest";

function exclusion(overrides: Partial<AiPickExclusion>): AiPickExclusion {
  return {
    match_id: "mth_x",
    league: "Continental Premier",
    market: "1X2",
    selection: "HOME",
    status: "excluded",
    reason: "negative_ev",
    detail: "Expected value is negative.",
    ...overrides,
  };
}

describe("summarizeAiPicks", () => {
  it("reports the engine total separately from what is displayed", () => {
    const page = aiPicks.slice(0, 2);
    const summary = summarizeAiPicks(page, 4);

    expect(summary.total).toBe(4);
    expect(summary.displayed).toBe(2);
  });

  it("picks the best opportunity by engine rank, not by page order", () => {
    const shuffled = [aiPicks[2], aiPicks[0], aiPicks[1]];
    const summary = summarizeAiPicks(shuffled, shuffled.length);

    expect(summary.best?.rank).toBe(1);
  });

  it("averages only the opportunities it was given", () => {
    const summary = summarizeAiPicks(aiPicks.slice(0, 2), 4);
    const expectedEv = (aiPicks[0].ev + aiPicks[1].ev) / 2;
    const expectedEdge = (aiPicks[0].edge + aiPicks[1].edge) / 2;

    expect(summary.averageEv).toBeCloseTo(expectedEv, 6);
    expect(summary.averageEdge).toBeCloseTo(expectedEdge, 6);
  });

  it("returns null averages instead of zero when there is nothing to average", () => {
    const summary = summarizeAiPicks([], 0);

    expect(summary.averageEv).toBeNull();
    expect(summary.averageEdge).toBeNull();
    expect(summary.best).toBeNull();
  });
});

describe("groupExclusions", () => {
  it("groups by reason, most frequent first", () => {
    const groups = groupExclusions([
      exclusion({ reason: "negative_ev", match_id: "a" }),
      exclusion({ reason: "stale_odds", match_id: "b" }),
      exclusion({ reason: "negative_ev", match_id: "c" }),
    ]);

    expect(groups.map((group) => [group.reason, group.count])).toEqual([
      ["negative_ev", 2],
      ["stale_odds", 1],
    ]);
  });

  it("keeps a market-wide exclusion, which carries no selection", () => {
    const groups = groupExclusions([
      exclusion({ reason: "incomplete_market", selection: null }),
    ]);

    expect(groups[0].items[0].selection).toBeNull();
  });

  it("returns nothing when the engine rejected nothing", () => {
    expect(groupExclusions([])).toEqual([]);
  });
});

describe("describePage", () => {
  it("derives navigation from the server total, limit and offset", () => {
    const info = describePage(10, 6, 0);

    expect(info).toMatchObject({
      page: 1,
      pageCount: 2,
      hasPrevious: false,
      hasNext: true,
      rangeStart: 1,
      rangeEnd: 6,
    });
  });

  it("clamps the last page to the real total", () => {
    const info = describePage(10, 6, 6);

    expect(info).toMatchObject({ page: 2, hasNext: false, rangeStart: 7, rangeEnd: 10 });
  });

  it("shows an empty range rather than a phantom first item", () => {
    const info = describePage(0, 6, 0);

    expect(info).toMatchObject({ pageCount: 1, rangeStart: 0, rangeEnd: 0, hasNext: false });
  });
});
