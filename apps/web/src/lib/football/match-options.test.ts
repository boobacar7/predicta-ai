import { firstFootballMatchId, footballMatchOptions } from "@/lib/football/match-options";
import type { AiPick, MatchSummary } from "@/types/api";
import { describe, expect, it } from "vitest";

function match(id: string, home: string, away: string): MatchSummary {
  return {
    id,
    home: { short_name: home },
    away: { short_name: away },
  } as MatchSummary;
}

function pick(matchId: string, home: string | null, away: string | null): AiPick {
  return { match_id: matchId, home_team: home, away_team: away } as AiPick;
}

describe("footballMatchOptions", () => {
  it("merges catalogue matches and picks without importing fixtures", () => {
    const options = footballMatchOptions({
      matches: [match("mth_a", "Northgate", "Harbor")],
      picks: [pick("mth_lincoln", "Lincoln Red Imps", "Inter Club d'Escaldes")],
      currentId: "mth_deep",
    });

    expect(options.map((item) => item.id)).toEqual(["mth_a", "mth_lincoln", "mth_deep"]);
    expect(options[1]?.label).toContain("Lincoln");
  });
});

describe("firstFootballMatchId", () => {
  it("prefers the requested match_id", () => {
    expect(
      firstFootballMatchId({
        requested: "mth_from_url",
        picks: [pick("mth_pick", "A", "B")],
        matches: [match("mth_cat", "C", "D")],
      }),
    ).toBe("mth_from_url");
  });

  it("falls back to the first published pick, then the catalogue", () => {
    expect(firstFootballMatchId({ picks: [pick("mth_pick", "A", "B")] })).toBe("mth_pick");
    expect(firstFootballMatchId({ matches: [match("mth_cat", "C", "D")] })).toBe("mth_cat");
    expect(firstFootballMatchId({})).toBe("");
  });
});
