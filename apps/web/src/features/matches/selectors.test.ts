import { searchMatches, upcomingDays } from "@/features/matches/selectors";
import type { MatchSummary } from "@/types/api";
import { describe, expect, it } from "vitest";

function match(id: string, home: string, away: string): MatchSummary {
  return {
    id,
    home: { name: home, short_name: home.split(" ")[0] },
    away: { name: away, short_name: away.split(" ")[0] },
  } as MatchSummary;
}

const fixtures = [
  match("a", "Riverside United", "Oakmont City"),
  match("b", "Härbor Athletic", "Northgate FC"),
  match("c", "Silverpark", "Westbridge"),
];

describe("searchMatches", () => {
  it("returns every match for an empty or whitespace query", () => {
    expect(searchMatches(fixtures, "")).toHaveLength(3);
    expect(searchMatches(fixtures, "   ")).toHaveLength(3);
  });

  it("matches either side of the fixture", () => {
    expect(searchMatches(fixtures, "Oakmont").map((item) => item.id)).toEqual(["a"]);
    expect(searchMatches(fixtures, "Riverside").map((item) => item.id)).toEqual(["a"]);
  });

  it("ignores case", () => {
    expect(searchMatches(fixtures, "sILVERPARK").map((item) => item.id)).toEqual(["c"]);
  });

  it("ignores accents, so a French keyboard finds an unaccented name and vice versa", () => {
    expect(searchMatches(fixtures, "harbor").map((item) => item.id)).toEqual(["b"]);
    expect(searchMatches(fixtures, "härbor").map((item) => item.id)).toEqual(["b"]);
  });

  it("returns nothing when no team matches, rather than falling back to everything", () => {
    expect(searchMatches(fixtures, "zzz")).toHaveLength(0);
  });

  it("does not mutate the input array", () => {
    const input = [...fixtures];
    searchMatches(input, "Oakmont");

    expect(input).toHaveLength(3);
  });
});

describe("upcomingDays", () => {
  it("returns the requested number of consecutive ISO dates", () => {
    const days = upcomingDays(7);

    expect(days).toHaveLength(7);
    expect(days.every((day) => /^\d{4}-\d{2}-\d{2}$/.test(day))).toBe(true);
  });

  it("starts at the injected mock clock, keeping the calendar deterministic", () => {
    expect(upcomingDays(1)).toEqual(["2026-09-09"]);
  });

  it("advances by exactly one day", () => {
    const [first, second] = upcomingDays(2);

    expect(second).toBe("2026-09-10");
    expect(first).toBe("2026-09-09");
  });
});
