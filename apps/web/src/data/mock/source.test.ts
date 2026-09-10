import { MockDataSource } from "@/data/mock/source";
import { DataSourceError } from "@/lib/api/errors";
import type { MockScenario } from "@/types/api";
import { describe, expect, it } from "vitest";

/** Latency is disabled so tests stay fast and deterministic. */
function source(scenario: MockScenario = "success") {
  return new MockDataSource({ scenario, latencyMs: 0 });
}

describe("envelopes", () => {
  it("marks every response as mock so it cannot be mistaken for live data", async () => {
    const dashboard = await source().getDashboard();
    const matches = await source().getMatches();

    expect(dashboard.data_mode).toBe("mock");
    expect(matches.data_mode).toBe("mock");
  });

  it("uses the injected clock, so fixtures are stable across runs", async () => {
    const first = await source().getDashboard();
    const second = await source().getDashboard();

    expect(first.generated_at).toBe(second.generated_at);
  });
});

describe("filters", () => {
  it("narrows matches by sport", async () => {
    const result = await source().getMatches({ sport: "football" });

    expect(result.data.items.length).toBeGreaterThan(0);
    expect(result.data.items.every((match) => match.sport === "football")).toBe(true);
  });

  it("treats an 'all' filter as no filter", async () => {
    const all = await source().getMatches({ sport: "all" });
    const none = await source().getMatches();

    expect(all.data.total).toBe(none.data.total);
  });

  it("narrows matches by status", async () => {
    const result = await source().getMatches({ status: "live" });

    expect(result.data.items.every((match) => match.status === "live")).toBe(true);
  });

  it("searches teams case- and accent-insensitively on the name", async () => {
    const all = await source().getTeams();
    const target = all.data.items[0]!;
    const result = await source().getTeams({ query: target.name.toUpperCase() });

    expect(result.data.items.map((team) => team.id)).toContain(target.id);
  });

  it("reports a total consistent with the returned page", async () => {
    const result = await source().getLeagues();

    expect(result.data.total).toBe(result.data.items.length);
  });
});

describe("missing entities", () => {
  it("raises a non-retryable not_found error", async () => {
    const error = (await source()
      .getMatch("mth_does_not_exist")
      .catch((caught: unknown) => caught)) as DataSourceError;

    expect(error).toBeInstanceOf(DataSourceError);
    expect(error.kind).toBe("not_found");
    expect(error.retryable).toBe(false);
  });

  it("raises not_found for an unknown team, league and player alike", async () => {
    const kinds = await Promise.all(
      [
        source().getTeam("nope"),
        source().getLeague("nope"),
        source().getPlayer("nope"),
      ].map((promise) => promise.catch((error: unknown) => (error as DataSourceError).kind)),
    );

    expect(kinds).toEqual(["not_found", "not_found", "not_found"]);
  });
});

describe("scenarios", () => {
  it("empty returns no results rather than an error", async () => {
    const matches = await source("empty").getMatches();
    const picks = await source("empty").getPicks();
    const value = await source("empty").getValue();

    expect(matches.data.items).toHaveLength(0);
    expect(picks.data.items).toHaveLength(0);
    expect(value.data.items).toHaveLength(0);
  });

  it("stale keeps the payload but degrades its freshness", async () => {
    const result = await source("stale").getMatches();

    expect(result.data.items.length).toBeGreaterThan(0);
    expect(result.data.items.every((match) => match.quality.availability === "stale")).toBe(true);
  });

  it("partial keeps the payload and flags some predictions as incomplete", async () => {
    const result = await source("partial").getMatches();
    const flagged = result.data.items.filter(
      (match) => match.prediction_preview?.quality.availability === "partial",
    );

    expect(result.data.items.length).toBeGreaterThan(0);
    expect(flagged.length).toBeGreaterThan(0);
  });

  it("error simulates a provider failure", async () => {
    const error = (await source("error")
      .getDashboard()
      .catch((caught: unknown) => caught)) as DataSourceError;

    expect(error.kind).toBe("mock_scenario");
  });

  it("does not leak a scenario transform back into the shared fixtures", async () => {
    await source("stale").getMatches();
    const clean = await source("success").getMatches();

    expect(clean.data.items.every((match) => match.quality.availability !== "stale")).toBe(true);
  });
});

describe("data integrity", () => {
  /**
   * A gap must stay a gap. If a fixture ever replaced an unknown measurement
   * with 0, the UI would present an invented figure as a real one.
   */
  it("expresses unavailable statistics as null, never as zero", async () => {
    const team = await source().getTeam("tm_riverside");
    const unavailable = team.data.stats.filter(
      (stat) => stat.quality.availability === "unavailable",
    );

    expect(unavailable.length).toBeGreaterThan(0);
    expect(unavailable.every((stat) => stat.value === null)).toBe(true);
  });

  it("attaches a provenance and observation time to available measurements", async () => {
    const team = await source().getTeam("tm_riverside");
    const available = team.data.stats.filter((stat) => stat.quality.availability === "available");

    expect(available.length).toBeGreaterThan(0);
    expect(available.every((stat) => stat.quality.source && stat.quality.observed_at)).toBe(true);
  });

  it("publishes predictions with a model version and a data cutoff", async () => {
    const result = await source().getMatches();
    const previews = result.data.items
      .map((match) => match.prediction_preview)
      .filter((preview) => preview !== null);

    expect(previews.length).toBeGreaterThan(0);
    expect(previews.every((preview) => preview.model_version && preview.cutoff_at)).toBe(true);
  });
});

/**
 * The mock must reproduce the engine's own semantics, verified against a live
 * response, or the UI would be built against behaviour the API does not have.
 */
describe("football AI picks", () => {
  it("ranks globally and paginates without renumbering the page", async () => {
    const all = await source().getFootballAiPicks();
    const second = await source().getFootballAiPicks({ limit: 2, offset: 2 });

    expect(all.data.items[0].rank).toBe(1);
    expect(second.data.items).toHaveLength(2);
    // `total` counts every eligible opportunity, not the page.
    expect(second.data.total).toBe(all.data.total);
    expect(second.data.offset).toBe(2);
  });

  it("filters by league name, ignoring case", async () => {
    const result = await source().getFootballAiPicks({ league: "northern championship" });

    expect(result.data.items.length).toBeGreaterThan(0);
    expect(result.data.items.every((pick) => pick.league === "Northern Championship")).toBe(true);
  });

  it("returns an empty result for a date with no candidate", async () => {
    const result = await source().getFootballAiPicks({ date: "1999-01-01" });

    expect(result.data.items).toHaveLength(0);
    expect(result.data.total).toBe(0);
  });

  /**
   * A threshold must not merely hide rows. The engine re-evaluates eligibility
   * and reports what it rejected, which is what lets the UI explain an empty page.
   */
  it("moves selections below a threshold into exclusions rather than dropping them", async () => {
    const baseline = await source().getFootballAiPicks();
    const filtered = await source().getFootballAiPicks({ min_edge: 0.05 });

    expect(filtered.data.items.length).toBeLessThan(baseline.data.items.length);
    expect(filtered.data.exclusions.length).toBeGreaterThan(baseline.data.exclusions.length);
    expect(filtered.data.exclusions.some((item) => item.reason === "below_minimum_edge")).toBe(true);
  });

  it("echoes the thresholds it applied", async () => {
    const result = await source().getFootballAiPicks({ min_edge: 0.02, min_ev: 0.03 });

    expect(result.data.metadata.minimum_edge).toBe(0.02);
    expect(result.data.metadata.minimum_ev).toBe(0.03);
  });

  it("reports the EV rule first when a selection fails both thresholds", async () => {
    const result = await source().getFootballAiPicks({ min_edge: 0.9, min_ev: 0.9 });

    expect(result.data.items).toHaveLength(0);
    expect(result.data.exclusions.every((item) => item.reason !== "below_minimum_edge")).toBe(true);
  });

  it("keeps every pick on the candidate model, never claiming a promoted one", async () => {
    const result = await source().getFootballAiPicks();

    expect(result.data_mode).toBe("mock");
    expect(result.data.items.every((pick) => pick.model_status === "candidate")).toBe(true);
  });

  it("returns no opportunity in the empty scenario", async () => {
    const result = await source("empty").getFootballAiPicks();

    expect(result.data.items).toHaveLength(0);
    expect(result.data.total).toBe(0);
  });

  it("fails with a retryable error in the error scenario", async () => {
    await expect(source("error").getFootballAiPicks()).rejects.toBeInstanceOf(DataSourceError);
  });
});
