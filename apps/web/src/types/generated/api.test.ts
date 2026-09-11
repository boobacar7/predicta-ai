import type { components, paths } from "@/types/generated/api";
import { expectTypeOf } from "vitest";
import { describe, expect, it } from "vitest";

/**
 * Guards the generated OpenAPI surface that the handwritten `api.ts` aliases.
 *
 * If `contracts/openapi.yaml` drops `home_team` or makes it non-nullable, this
 * file fails at typecheck time rather than letting the UI drift again.
 */

type GeneratedAiPick = components["schemas"]["AiPick"];
type GeneratedIdentity = components["schemas"]["HistoricalMatchIdentity"];
type GeneratedAnalyst = components["schemas"]["FootballAiAnalystReport"];

describe("generated OpenAPI types", () => {
  it("keeps the football product HTTP paths", () => {
    expectTypeOf<paths>().toHaveProperty("/football/predictions/{match_id}");
    expectTypeOf<paths>().toHaveProperty("/football/value/{match_id}");
    expectTypeOf<paths>().toHaveProperty("/football/ai-picks");
    expectTypeOf<paths>().toHaveProperty("/football/ai-analyst/{match_id}");
  });

  it("publishes nullable team labels and a required kickoff on AiPick", () => {
    expectTypeOf<GeneratedAiPick["home_team"]>().toEqualTypeOf<string | null>();
    expectTypeOf<GeneratedAiPick["away_team"]>().toEqualTypeOf<string | null>();
    expectTypeOf<GeneratedAiPick["kickoff_at"]>().toEqualTypeOf<string>();
    expectTypeOf<GeneratedAiPick["league"]>().toEqualTypeOf<string>();
  });

  it("publishes HistoricalMatchIdentity as a structural-only match payload", () => {
    expectTypeOf<GeneratedIdentity["resource_scope"]>().toEqualTypeOf<"structural_identity">();
    expectTypeOf<GeneratedIdentity["home_team"]>().toEqualTypeOf<string | null>();
    expectTypeOf<GeneratedIdentity["away_team"]>().toEqualTypeOf<string | null>();
    expectTypeOf<GeneratedIdentity>().not.toHaveProperty("score");
    expectTypeOf<GeneratedIdentity>().not.toHaveProperty("timeline");
  });

  it("accepts the identity-fixed engine payload without extra fields", () => {
    const pick = {
      match_id: "mth_football-sportmonks-19719892",
      sport: "football",
      home_team: "Lincoln Red Imps",
      away_team: "Inter Club d'Escaldes",
      league: "Champions League",
      kickoff_at: "2026-07-07T16:00:00Z",
      market: "1X2",
      selection: "AWAY",
      model_probability: 0.31261487997008847,
      odds: 5,
      implied_probability: 0.2,
      no_vig_probability: 0.21052631578947367,
      edge: 0.11261487997008847,
      ev: 0.5630743998504424,
      opportunity_score: 0.6756892798205308,
      rank: 1,
      odds_source: "predicta-mock-odds-v0.1",
      model_version: "football-elo-v1-candidate",
      model_status: "candidate",
      value_engine_version: "value-engine-0.1",
      ai_picks_version: "ai-picks-0.1",
      cutoff_at: "2026-07-07T16:00:00Z",
      generated_at: "2026-09-09T18:00:00Z",
      data_mode: "mock",
      status: "eligible",
    } as const satisfies GeneratedAiPick;

    expect(pick.home_team).toBe("Lincoln Red Imps");
  });

  it("keeps model_favorite distinct from value_selection on the analyst report", () => {
    expectTypeOf<GeneratedAnalyst["model_favorite"]>().toEqualTypeOf<"HOME" | "DRAW" | "AWAY">();
    expectTypeOf<GeneratedAnalyst["value"]["value_selection"]>().toEqualTypeOf<
      "HOME" | "DRAW" | "AWAY" | null
    >();
    expectTypeOf<GeneratedAnalyst["home_team"]>().toEqualTypeOf<string | null>();
  });
});
