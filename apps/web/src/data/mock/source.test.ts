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
