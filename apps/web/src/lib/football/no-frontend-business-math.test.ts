import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

function source(relative: string): string {
  const candidates = [
    resolve(process.cwd(), "src", relative),
    resolve(process.cwd(), "apps/web/src", relative),
  ];
  const path = candidates.find((item) => existsSync(item));
  if (!path) {
    throw new Error(`Missing source file ${relative}`);
  }
  return readFileSync(path, "utf8");
}

const PRODUCT_VIEWS = [
  "features/dashboard/dashboard-view.tsx",
  "features/matches/match-detail-view.tsx",
  "features/value/value-finder-view.tsx",
  "features/picks/ai-picks-view.tsx",
  "features/ai-analyst/ai-analyst-view.tsx",
] as const;

const FORBIDDEN_MATH = [
  /1\s*\/\s*(odds|row\.odds|pick\.odds)/,
  /model_probability\s*\*\s*.*odds/,
  /opportunity_score\s*=/,
  /implied_probability\s*=\s*1/,
  /no_vig_probability\s*=\s*.*\/\s*/,
  /Math\.max\([^)]*home_probability/,
];

describe("football product views do not recompute business math", () => {
  it.each(PRODUCT_VIEWS)("%s copies published figures", (relative) => {
    const text = source(relative);
    for (const pattern of FORBIDDEN_MATH) {
      expect(text).not.toMatch(pattern);
    }
  });

  it("routes the Lincoln journey through canonical football endpoints", () => {
    const http = source("data/http/source.ts");
    expect(http).toContain("/football/predictions/");
    expect(http).toContain("/football/value/");
    expect(http).toContain('"/football/ai-picks"');
    expect(http).toContain("/football/ai-analyst/");

    expect(source("features/dashboard/dashboard-view.tsx")).toContain("useFootballAiPicks");
    expect(source("features/dashboard/dashboard-view.tsx")).toContain("useFootballValue");
    expect(source("features/matches/match-detail-view.tsx")).toContain("useFootballPrediction");
    expect(source("features/matches/match-detail-view.tsx")).toContain("useFootballValue");
    expect(source("features/value/value-finder-view.tsx")).toContain("useFootballValue");
    expect(source("features/value/value-finder-view.tsx")).not.toContain("useValueOpportunities");
    expect(source("features/picks/ai-picks-view.tsx")).toContain("useFootballAiPicks");
    expect(source("features/ai-analyst/ai-analyst-view.tsx")).toContain("useFootballAiAnalyst");
  });

  it("does not infer a favorite in the prediction panel", () => {
    const panel = source("components/domain/football-prediction-panel.tsx");
    expect(panel).not.toContain("model_favorite");
    expect(panel).not.toContain("Math.max");
  });
});
