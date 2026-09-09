import { HttpClient } from "@/data/http/client";
import { DataSourceError } from "@/lib/api/errors";
import { describe, expect, it, vi } from "vitest";

const BASE_URL = "https://api.example.test/api/v1";

function jsonResponse(body: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(body), {
    status: 200,
    headers: { "Content-Type": "application/json" },
    ...init,
  });
}

function envelope<T>(data: T) {
  return {
    data_mode: "live",
    generated_at: "2026-09-09T18:00:00.000Z",
    request_id: "req_test",
    data,
  };
}

function clientWith(fetchImpl: typeof fetch) {
  return new HttpClient({ baseUrl: BASE_URL, requestTimeoutMs: 1_000, fetchImpl });
}

/** Typed spy so `mock.calls` keeps the `fetch` argument tuple. */
function spyFetch(respond: () => Response) {
  return vi.fn<(url: string, init: RequestInit) => Promise<Response>>(async () => respond());
}

describe("request construction", () => {
  it("appends only the filters that carry a value", async () => {
    const fetchImpl = spyFetch(() => jsonResponse(envelope({ items: [], total: 0 })));
    await clientWith(fetchImpl as unknown as typeof fetch).get("/matches", {
      sport: "football",
      league_id: "all",
      date: undefined,
      status: "",
    });

    const url = new URL(fetchImpl.mock.calls[0]![0]);

    expect(url.pathname).toBe("/api/v1/matches");
    expect(url.searchParams.get("sport")).toBe("football");
    // "all" means "no filter" and must not be sent to the API.
    expect(url.searchParams.has("league_id")).toBe(false);
    expect(url.searchParams.has("date")).toBe(false);
    expect(url.searchParams.has("status")).toBe(false);
  });

  it("sends a JSON body on post", async () => {
    const fetchImpl = spyFetch(() => jsonResponse(envelope({ ok: true })));
    await clientWith(fetchImpl as unknown as typeof fetch).post("/ai/analyze", {
      match_id: "mth_1",
    });

    const init = fetchImpl.mock.calls[0]![1];

    expect(init.method).toBe("POST");
    expect(init.body).toBe(JSON.stringify({ match_id: "mth_1" }));
  });
});

describe("RFC 9457 problem details", () => {
  it("maps 404 to a non-retryable not_found error", async () => {
    const fetchImpl = async () =>
      jsonResponse(
        { title: "Not Found", detail: "Match inconnu.", status: 404, request_id: "req_404" },
        { status: 404 },
      );

    const error = await clientWith(fetchImpl as unknown as typeof fetch)
      .get("/matches/unknown")
      .catch((caught: unknown) => caught);

    expect(error).toBeInstanceOf(DataSourceError);
    const dataError = error as DataSourceError;
    expect(dataError.kind).toBe("not_found");
    expect(dataError.message).toBe("Match inconnu.");
    expect(dataError.requestId).toBe("req_404");
    expect(dataError.retryable).toBe(false);
  });

  it("maps 500 to a retryable server error", async () => {
    const fetchImpl = async () => jsonResponse({ title: "Boom" }, { status: 500 });

    const error = (await clientWith(fetchImpl as unknown as typeof fetch)
      .get("/matches")
      .catch((caught: unknown) => caught)) as DataSourceError;

    expect(error.kind).toBe("server");
    expect(error.retryable).toBe(true);
  });

  it("survives an error response that is not valid JSON", async () => {
    const fetchImpl = async () => new Response("<html>502</html>", { status: 502 });

    const error = (await clientWith(fetchImpl as unknown as typeof fetch)
      .get("/matches")
      .catch((caught: unknown) => caught)) as DataSourceError;

    expect(error.kind).toBe("server");
    expect(error.status).toBe(502);
  });
});

describe("envelope validation", () => {
  it("accepts a well-formed envelope and preserves data_mode", async () => {
    const fetchImpl = async () => jsonResponse(envelope({ total: 1 }));
    const result = await clientWith(fetchImpl as unknown as typeof fetch).get<{ total: number }>(
      "/matches",
    );

    expect(result.data_mode).toBe("live");
    expect(result.data.total).toBe(1);
  });

  /**
   * `data_mode` is what stops a mock payload being rendered as live data during
   * the migration, so a response without it is rejected rather than trusted.
   */
  it("rejects a payload that is missing data_mode", async () => {
    const fetchImpl = async () =>
      jsonResponse({ generated_at: "2026-09-09T18:00:00.000Z", request_id: "r", data: {} });

    const error = (await clientWith(fetchImpl as unknown as typeof fetch)
      .get("/matches")
      .catch((caught: unknown) => caught)) as DataSourceError;

    expect(error.kind).toBe("invalid_response");
    expect(error.retryable).toBe(false);
  });

  it("rejects a bare payload returned without an envelope", async () => {
    const fetchImpl = async () => jsonResponse([{ id: "mth_1" }]);

    const error = (await clientWith(fetchImpl as unknown as typeof fetch)
      .get("/matches")
      .catch((caught: unknown) => caught)) as DataSourceError;

    expect(error.kind).toBe("invalid_response");
  });
});

describe("transport failures", () => {
  it("normalises a network failure into a retryable error", async () => {
    const fetchImpl = async () => {
      throw new TypeError("Failed to fetch");
    };

    const error = (await clientWith(fetchImpl as unknown as typeof fetch)
      .get("/matches")
      .catch((caught: unknown) => caught)) as DataSourceError;

    expect(error.kind).toBe("network");
    expect(error.retryable).toBe(true);
  });

  it("aborts a request that exceeds the timeout budget", async () => {
    const client = new HttpClient({
      baseUrl: BASE_URL,
      requestTimeoutMs: 10,
      fetchImpl: ((_url: string, init: RequestInit) =>
        new Promise((_resolve, reject) => {
          init.signal?.addEventListener("abort", () =>
            reject(new DOMException("Aborted", "AbortError")),
          );
        })) as unknown as typeof fetch,
    });

    const error = (await client.get("/matches").catch((caught: unknown) => caught)) as DataSourceError;

    expect(error.kind).toBe("network");
    expect(error.message).toMatch(/délai/);
  });
});
