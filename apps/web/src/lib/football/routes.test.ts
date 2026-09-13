import nextConfig from "../../../next.config";
import {
  FOOTBALL_PATHS,
  LEGACY_FOOTBALL_REDIRECTS,
  P1_SPORT,
  footballAnalystPath,
  footballMatchPath,
  isFootballNavActive,
} from "@/lib/football/routes";
import { navSections } from "@/lib/navigation";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

describe("canonical football routes", () => {
  it("locks P1 to /football/*", () => {
    expect(P1_SPORT).toBe("football");
    expect(FOOTBALL_PATHS).toEqual({
      dashboard: "/football",
      matches: "/football/matches",
      aiPicks: "/football/ai-picks",
      value: "/football/value",
      aiAnalyst: "/football/ai-analyst",
    });
  });

  it("builds match and analyst deep links with match_id", () => {
    expect(footballMatchPath("mth_football-sportmonks-19719892")).toBe(
      "/football/matches/mth_football-sportmonks-19719892",
    );
    expect(footballAnalystPath("mth_football-sportmonks-19719892")).toBe(
      "/football/ai-analyst?match_id=mth_football-sportmonks-19719892",
    );
    expect(footballAnalystPath()).toBe("/football/ai-analyst");
  });

  it("does not treat /football as active on nested football routes", () => {
    expect(isFootballNavActive("/football", FOOTBALL_PATHS.dashboard)).toBe(true);
    expect(isFootballNavActive("/football/matches", FOOTBALL_PATHS.dashboard)).toBe(false);
    expect(isFootballNavActive("/football/matches/abc", FOOTBALL_PATHS.matches)).toBe(true);
  });

  it("exposes only football destinations in P1 navigation", () => {
    const hrefs = navSections.flatMap((section) => section.items.map((item) => item.href));
    expect(hrefs).toEqual([
      "/football",
      "/football/matches",
      "/football/ai-picks",
      "/football/value",
      "/football/ai-analyst",
    ]);
    expect(hrefs.join(" ")).not.toMatch(/basketball|tennis|analytics|performance|leagues|teams|players/i);
  });

  it("redirects legacy prototype paths onto /football/*", async () => {
    const redirects = await nextConfig.redirects?.();
    expect(redirects).toEqual(LEGACY_FOOTBALL_REDIRECTS);
  });

  it("has an App Router page for each canonical football surface", () => {
    const pages = [
      "app/football/page.tsx",
      "app/football/matches/page.tsx",
      "app/football/matches/[id]/page.tsx",
      "app/football/ai-picks/page.tsx",
      "app/football/value/page.tsx",
      "app/football/ai-analyst/page.tsx",
    ];

    for (const relative of pages) {
      const path = resolve(process.cwd(), "src", relative);
      expect(existsSync(path), `${relative} is missing`).toBe(true);
    }
  });
});
