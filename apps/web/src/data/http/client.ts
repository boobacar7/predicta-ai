import {
  DataSourceError,
  kindFromStatus,
  toDataSourceError,
  type ProblemDetails,
} from "@/lib/api/errors";
import type { DataMode, Envelope } from "@/types/api";

/**
 * Minimal typed HTTP client for the PREDICTA API.
 *
 * It owns the transport concerns the contract documents: the `/api/v1` prefix,
 * snake_case JSON, RFC 9457 Problem Details on failure, `request_id` propagation
 * and a bounded timeout. It performs no business logic and no reshaping — the
 * response envelope reaches callers exactly as the server produced it.
 */

export type QueryParams = Record<string, string | number | boolean | null | undefined>;

export interface HttpClientOptions {
  /** Base URL including the version prefix, without a trailing slash. */
  baseUrl: string;
  requestTimeoutMs: number;
  /** Injectable for tests. Defaults to the platform `fetch`. */
  fetchImpl?: typeof fetch;
}

export class HttpClient {
  private readonly baseUrl: string;
  private readonly requestTimeoutMs: number;
  private readonly fetchImpl: typeof fetch;

  constructor({ baseUrl, requestTimeoutMs, fetchImpl }: HttpClientOptions) {
    this.baseUrl = baseUrl.replace(/\/+$/, "");
    this.requestTimeoutMs = requestTimeoutMs;
    this.fetchImpl = fetchImpl ?? globalThis.fetch.bind(globalThis);
  }

  get<T>(path: string, params?: QueryParams): Promise<Envelope<T>> {
    return this.request<T>("GET", path, params);
  }

  post<T>(path: string, body: unknown): Promise<Envelope<T>> {
    return this.request<T>("POST", path, undefined, body);
  }

  private async request<T>(
    method: "GET" | "POST",
    path: string,
    params?: QueryParams,
    body?: unknown,
  ): Promise<Envelope<T>> {
    const url = this.buildUrl(path, params);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.requestTimeoutMs);

    let response: Response;

    try {
      response = await this.fetchImpl(url, {
        method,
        signal: controller.signal,
        headers: {
          Accept: "application/json",
          ...(body === undefined ? {} : { "Content-Type": "application/json" }),
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
      });
    } catch (error) {
      throw toDataSourceError(error);
    } finally {
      clearTimeout(timeout);
    }

    if (!response.ok) {
      throw await readProblem(response);
    }

    const payload: unknown = await response.json().catch((error: unknown) => {
      throw new DataSourceError({
        kind: "invalid_response",
        message: "La réponse du service de données n'est pas un JSON valide.",
        cause: error,
      });
    });

    return assertEnvelope<T>(payload, url);
  }

  private buildUrl(path: string, params?: QueryParams): string {
    const url = new URL(`${this.baseUrl}${path}`);

    for (const [key, value] of Object.entries(params ?? {})) {
      // A filter that is absent, or explicitly "all", is simply not sent.
      if (value === undefined || value === null || value === "" || value === "all") continue;
      url.searchParams.set(key, String(value));
    }

    return url.toString();
  }
}

async function readProblem(response: Response): Promise<DataSourceError> {
  const problem = await response
    .json()
    .then((value: unknown) => (isProblemDetails(value) ? value : undefined))
    .catch(() => undefined);

  return new DataSourceError({
    kind: kindFromStatus(response.status),
    message: problem?.detail ?? problem?.title,
    status: response.status,
    requestId: problem?.request_id ?? response.headers.get("x-request-id") ?? undefined,
    problem,
  });
}

function isProblemDetails(value: unknown): value is ProblemDetails {
  return typeof value === "object" && value !== null;
}

const DATA_MODES: readonly DataMode[] = ["mock", "live"];

/**
 * Guards the response envelope.
 *
 * `data_mode` in particular must survive the transport: it is what prevents a
 * mock payload from being silently rendered as live data during the migration.
 */
function assertEnvelope<T>(payload: unknown, url: string): Envelope<T> {
  if (typeof payload !== "object" || payload === null) {
    throw invalidEnvelope(url, "la réponse n'est pas un objet");
  }

  const candidate = payload as Partial<Envelope<T>>;

  if (!DATA_MODES.includes(candidate.data_mode as DataMode)) {
    throw invalidEnvelope(url, "champ data_mode absent ou inconnu");
  }

  if (typeof candidate.generated_at !== "string") {
    throw invalidEnvelope(url, "champ generated_at absent");
  }

  if (typeof candidate.request_id !== "string") {
    throw invalidEnvelope(url, "champ request_id absent");
  }

  if (!("data" in candidate)) {
    throw invalidEnvelope(url, "champ data absent");
  }

  return candidate as Envelope<T>;
}

function invalidEnvelope(url: string, reason: string): DataSourceError {
  return new DataSourceError({
    kind: "invalid_response",
    message: `Enveloppe invalide reçue de ${url} : ${reason}.`,
  });
}
