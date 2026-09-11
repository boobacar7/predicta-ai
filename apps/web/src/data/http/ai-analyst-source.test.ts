import { HttpDataSource } from "@/data/http/source";
import { lincolnAnalystReport } from "@/data/mock/ai-analyst";
import { describe, expect, it, vi } from "vitest";

const BASE_URL = "https://api.example.test/api/v1";

function sourceWith(fetchImpl: typeof fetch) {
  return new HttpDataSource({
    baseUrl: BASE_URL,
    requestTimeoutMs: 1_000,
    fetchImpl,
  });
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

describe("HttpDataSource.getFootballAiAnalyst", () => {
  it("calls GET /football/ai-analyst/{match_id}", async () => {
    const fetchImpl = respondWith({
      data_mode: "live",
      generated_at: "2026-09-09T18:00:00Z",
      request_id: "req_test",
      data: lincolnAnalystReport,
    });

    await sourceWith(fetchImpl).getFootballAiAnalyst("mth_football-sportmonks-19719892");

    const url = new URL(vi.mocked(fetchImpl).mock.calls[0]![0] as string);
    expect(url.pathname).toBe("/api/v1/football/ai-analyst/mth_football-sportmonks-19719892");
  });

  it("forwards cutoff_at and omits it when absent", async () => {
    const fetchImpl = respondWith({
      data_mode: "live",
      generated_at: "2026-09-09T18:00:00Z",
      request_id: "req_test",
      data: lincolnAnalystReport,
    });

    await sourceWith(fetchImpl).getFootballAiAnalyst("mth_1", "2026-07-07T16:00:00Z");
    const withCutoff = new URL(vi.mocked(fetchImpl).mock.calls[0]![0] as string);
    expect(withCutoff.searchParams.get("cutoff_at")).toBe("2026-07-07T16:00:00Z");

    await sourceWith(fetchImpl).getFootballAiAnalyst("mth_1");
    const without = new URL(vi.mocked(fetchImpl).mock.calls[1]![0] as string);
    expect(without.searchParams.has("cutoff_at")).toBe(false);
  });

  it("preserves a live data_mode so mock fixtures cannot be labelled live", async () => {
    const fetchImpl = respondWith({
      data_mode: "live",
      generated_at: "2026-09-09T18:00:00Z",
      request_id: "req_test",
      data: lincolnAnalystReport,
    });

    const response = await sourceWith(fetchImpl).getFootballAiAnalyst("mth_1");
    expect(response.data_mode).toBe("live");
  });

  it("surfaces an RFC 9457 409 without replacing it by a fixture", async () => {
    const fetchImpl = respondWith(
      {
        type: "/problems/temporal-leakage",
        title: "Temporal leakage",
        status: 409,
        detail: "cutoff after point-in-time",
        request_id: "req_409",
      },
      409,
    );

    await expect(sourceWith(fetchImpl).getFootballAiAnalyst("mth_1", "2026-07-07T16:00:01Z")).rejects.toMatchObject({
      status: 409,
      requestId: "req_409",
      message: "cutoff after point-in-time",
    });
  });
});
