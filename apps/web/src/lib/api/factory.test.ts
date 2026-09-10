import { createDataSource, resolveKind } from "@/lib/api/factory";
import { DATA_RESOURCES, type DataResource, type DataSourceMode } from "@/lib/config";
import { describe, expect, it } from "vitest";

function modes(overrides: Partial<Record<DataResource, DataSourceMode>> = {}) {
  return Object.fromEntries(
    DATA_RESOURCES.map((resource) => [resource, overrides[resource] ?? "mock"]),
  ) as Record<DataResource, DataSourceMode>;
}

describe("resolveKind", () => {
  it("reports mock when nothing is migrated", () => {
    expect(resolveKind(modes())).toBe("mock");
  });

  it("reports http only once every resource is migrated", () => {
    const all = Object.fromEntries(
      DATA_RESOURCES.map((resource) => [resource, "http"]),
    ) as Record<DataResource, DataSourceMode>;

    expect(resolveKind(all)).toBe("http");
  });

  it("reports hybrid mid-migration, so the banner cannot claim a fully live build", () => {
    expect(resolveKind(modes({ matches: "http" }))).toBe("hybrid");
  });
});

describe("per-resource routing", () => {
  it("serves fixtures for resources that are still mocked", async () => {
    const source = createDataSource({ resourceModes: modes() });
    const result = await source.getMatches();

    expect(result.data_mode).toBe("mock");
  });

  /**
   * The point of hybrid mode: one endpoint can move to the API while its
   * neighbours keep serving fixtures, with no change to any view.
   */
  it("sends a migrated resource to http while its neighbours stay on fixtures", async () => {
    const source = createDataSource({
      resourceModes: modes({ performance: "http" }),
    });

    // No API is running in tests, so the HTTP route fails at the transport layer.
    // Reaching a network error proves the call was routed away from the fixtures.
    const performance = await source.getPerformance().catch((error: unknown) => error);
    const matches = await source.getMatches();

    expect(performance).toBeInstanceOf(Error);
    expect(matches.data_mode).toBe("mock");
  });

  it("binds the scenario to the mock resources", async () => {
    const source = createDataSource({ scenario: "empty", resourceModes: modes() });
    const result = await source.getMatches();

    expect(result.data.items).toHaveLength(0);
  });
});

describe("AI Picks routing", () => {
  /**
   * `GET /picks` and `GET /football/ai-picks` are separate resources in the
   * contract, so the engine can be pointed at the live API on its own.
   */
  it("routes the engine independently from the generic picks resource", async () => {
    const source = createDataSource({ resourceModes: modes({ football_ai_picks: "http" }) });

    // No API runs in tests: reaching a transport error proves the call left the fixtures.
    const engine = await source.getFootballAiPicks().catch((error: unknown) => error);
    const picks = await source.getPicks();

    expect(engine).toBeInstanceOf(Error);
    expect(picks.data_mode).toBe("mock");
    expect(resolveKind(modes({ football_ai_picks: "http" }))).toBe("hybrid");
  });

  it("serves the engine from fixtures by default", async () => {
    const source = createDataSource({ resourceModes: modes() });
    const result = await source.getFootballAiPicks();

    expect(result.data_mode).toBe("mock");
    expect(result.data.metadata.ai_picks_version).toBe("ai-picks-0.1");
  });
});
