import { HttpDataSource } from "@/data/http/source";
import { lincolnFootballPrediction, lincolnFootballValue } from "@/data/mock/football-engine";
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

const envelope = {
  data_mode: "mock",
  generated_at: "2026-09-09T18:00:00Z",
  request_id: "req_test",
};

describe("HttpDataSource football prediction and value", () => {
  it("calls GET /football/predictions/{match_id}", async () => {
    const fetchImpl = respondWith({ ...envelope, data: lincolnFootballPrediction });
    await sourceWith(fetchImpl).getFootballPrediction("mth_football-sportmonks-19719892");

    const url = new URL(vi.mocked(fetchImpl).mock.calls[0]![0] as string);
    expect(url.pathname).toBe("/api/v1/football/predictions/mth_football-sportmonks-19719892");
  });

  it("calls GET /football/value/{match_id} rather than legacy GET /value", async () => {
    const fetchImpl = respondWith({ ...envelope, data: lincolnFootballValue });
    await sourceWith(fetchImpl).getFootballValue("mth_football-sportmonks-19719892");

    const url = new URL(vi.mocked(fetchImpl).mock.calls[0]![0] as string);
    expect(url.pathname).toBe("/api/v1/football/value/mth_football-sportmonks-19719892");
    expect(url.pathname).not.toBe("/api/v1/value");
  });

  it("forwards cutoff_at when provided", async () => {
    const fetchImpl = respondWith({ ...envelope, data: lincolnFootballPrediction });
    await sourceWith(fetchImpl).getFootballPrediction(
      "mth_football-sportmonks-19719892",
      "2026-07-07T16:00:00Z",
    );

    const url = new URL(vi.mocked(fetchImpl).mock.calls[0]![0] as string);
    expect(url.searchParams.get("cutoff_at")).toBe("2026-07-07T16:00:00Z");
  });

  it("surfaces an RFC 9457 error instead of substituting a mock payload", async () => {
    const fetchImpl = respondWith(
      {
        type: "/problems/not-found",
        title: "Not Found",
        status: 404,
        detail: "Prediction not found",
        request_id: "req_err",
      },
      404,
    );

    await expect(sourceWith(fetchImpl).getFootballPrediction("mth_unknown")).rejects.toMatchObject({
      status: 404,
      requestId: "req_err",
    });
  });

  it("preserves data_mode from the envelope", async () => {
    const fetchImpl = respondWith({ ...envelope, data: lincolnFootballValue });
    const response = await sourceWith(fetchImpl).getFootballValue("mth_football-sportmonks-19719892");
    expect(response.data_mode).toBe("mock");
  });
});
