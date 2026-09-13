import { HttpDataSource } from "@/data/http/source";
import { describe, expect, it, vi } from "vitest";

const BASE_URL = "https://api.example.test/api/v1";

/**
 * Contract fidelity for `GET /football/ai-picks`.
 *
 * The engine's parameter names differ from the generic match filters: it takes
 * `league` as a name and has no `sport`. These tests pin that mapping, because
 * a silently wrong parameter name would not fail the request — the API would
 * simply ignore the filter and return unfiltered opportunities.
 */

function sourceWith(fetchImpl: typeof fetch) {
  const source = new HttpDataSource({
    baseUrl: BASE_URL,
    requestTimeoutMs: 1_000,
    fetchImpl,
  });

  return source;
}

function respondWith(body: unknown, status = 200): typeof fetch {
  return vi.fn(
    async () =>
      new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
  ) as unknown as typeof fetch;
}

function emptyResult() {
  return {
    data_mode: "mock",
    generated_at: "2026-09-09T18:00:00Z",
    request_id: "req_test",
    data: {
      items: [],
      exclusions: [],
      total: 0,
      limit: 20,
      offset: 0,
      metadata: {},
    },
  };
}

describe("HttpDataSource.getFootballAiPicks", () => {
  it("calls the engine route under the versioned prefix", async () => {
    const fetchImpl = respondWith(emptyResult());
    await sourceWith(fetchImpl).getFootballAiPicks();

    const url = new URL(vi.mocked(fetchImpl).mock.calls[0]![0] as string);

    expect(url.pathname).toBe("/api/v1/football/ai-picks");
  });

  it("sends the engine's own parameter names", async () => {
    const fetchImpl = respondWith(emptyResult());
    await sourceWith(fetchImpl).getFootballAiPicks({
      date: "2026-07-07",
      league: "Champions League",
      limit: 6,
      offset: 12,
      min_edge: 0.02,
      min_ev: 0.03,
    });

    const url = new URL(vi.mocked(fetchImpl).mock.calls[0]![0] as string);

    expect(url.searchParams.get("date")).toBe("2026-07-07");
    expect(url.searchParams.get("league")).toBe("Champions League");
    expect(url.searchParams.get("limit")).toBe("6");
    expect(url.searchParams.get("offset")).toBe("12");
    expect(url.searchParams.get("min_edge")).toBe("0.02");
    expect(url.searchParams.get("min_ev")).toBe("0.03");
    // The route serves football only and declares no sport parameter.
    expect(url.searchParams.has("sport")).toBe(false);
    expect(url.searchParams.has("league_id")).toBe(false);
  });

  it("omits absent filters instead of sending empty values", async () => {
    const fetchImpl = respondWith(emptyResult());
    await sourceWith(fetchImpl).getFootballAiPicks({ limit: 20 });

    const url = new URL(vi.mocked(fetchImpl).mock.calls[0]![0] as string);

    expect(url.searchParams.has("date")).toBe(false);
    expect(url.searchParams.has("league")).toBe(false);
    expect(url.searchParams.has("min_edge")).toBe(false);
  });

  /** A zero threshold is a real instruction and must reach the engine. */
  it("sends a zero threshold rather than dropping it", async () => {
    const fetchImpl = respondWith(emptyResult());
    await sourceWith(fetchImpl).getFootballAiPicks({ min_edge: 0, min_ev: 0 });

    const url = new URL(vi.mocked(fetchImpl).mock.calls[0]![0] as string);

    expect(url.searchParams.get("min_edge")).toBe("0");
    expect(url.searchParams.get("min_ev")).toBe("0");
  });

  it("surfaces the RFC 9457 problem returned for an out-of-range threshold", async () => {
    const fetchImpl = respondWith(
      {
        type: "/problems/validation",
        title: "Validation Error",
        status: 400,
        detail: "query.min_edge: Input should be less than 1",
        request_id: "req_4be7f609",
      },
      400,
    );

    await expect(sourceWith(fetchImpl).getFootballAiPicks({ min_edge: 5 })).rejects.toMatchObject({
      status: 400,
      requestId: "req_4be7f609",
      message: "query.min_edge: Input should be less than 1",
    });
  });

  it("preserves the data_mode of the response, so mock odds stay labelled", async () => {
    const fetchImpl = respondWith(emptyResult());
    const response = await sourceWith(fetchImpl).getFootballAiPicks();

    expect(response.data_mode).toBe("mock");
  });
});
