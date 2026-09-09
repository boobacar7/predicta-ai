/**
 * Transport-agnostic error model for the data access layer.
 *
 * Views never inspect HTTP status codes or fixture internals. They branch on
 * `kind` and `retryable`, so the same error surface works for mock and HTTP.
 */

export type DataSourceErrorKind =
  /** The request never produced a response (offline, DNS, timeout, abort). */
  | "network"
  /** The requested entity does not exist. */
  | "not_found"
  /** The server answered, but rejected or failed the request. */
  | "server"
  /** A response arrived but did not match the expected contract. */
  | "invalid_response"
  /** The endpoint is not wired yet in the active data source. */
  | "not_implemented"
  /** A mock scenario deliberately simulated a provider failure. */
  | "mock_scenario";

/** RFC 9457 Problem Details, the documented error format of the API. */
export interface ProblemDetails {
  type?: string;
  title?: string;
  status?: number;
  detail?: string;
  instance?: string;
  request_id?: string;
}

/**
 * Kinds worth attempting again.
 *
 * `mock_scenario` is included because it stands in for a provider outage: the
 * scenario exists to preview what a real transient failure looks like, retry
 * affordance included. A 404 or a contract violation is excluded, since the
 * identical request would fail the same way.
 */
const RETRYABLE_KINDS: ReadonlySet<DataSourceErrorKind> = new Set<DataSourceErrorKind>([
  "network",
  "server",
  "mock_scenario",
]);

/** Operator-facing default copy, in the product language (French). */
const DEFAULT_MESSAGES: Record<DataSourceErrorKind, string> = {
  network: "La connexion au service de données a échoué.",
  not_found: "Cette ressource est introuvable.",
  server: "Le service de données a renvoyé une erreur.",
  invalid_response: "La réponse reçue ne respecte pas le contrat attendu.",
  not_implemented: "Cet endpoint n'est pas encore branché sur l'API.",
  mock_scenario: "Scénario mock « erreur » : échec provider simulé volontairement.",
};

export interface DataSourceErrorOptions {
  kind: DataSourceErrorKind;
  message?: string;
  status?: number;
  requestId?: string;
  problem?: ProblemDetails;
  cause?: unknown;
}

export class DataSourceError extends Error {
  readonly kind: DataSourceErrorKind;
  readonly status?: number;
  readonly requestId?: string;
  readonly problem?: ProblemDetails;

  constructor({ kind, message, status, requestId, problem, cause }: DataSourceErrorOptions) {
    super(message ?? DEFAULT_MESSAGES[kind], { cause });
    this.name = "DataSourceError";
    this.kind = kind;
    this.status = status;
    this.requestId = requestId;
    this.problem = problem;
  }

  /** Whether retrying the identical request could plausibly succeed. */
  get retryable(): boolean {
    return RETRYABLE_KINDS.has(this.kind);
  }
}

export function isDataSourceError(error: unknown): error is DataSourceError {
  return error instanceof DataSourceError;
}

/** Maps an HTTP status onto the transport-agnostic error kinds. */
export function kindFromStatus(status: number): DataSourceErrorKind {
  if (status === 404) return "not_found";
  if (status === 501) return "not_implemented";
  return "server";
}

/**
 * Normalises anything thrown inside the data layer into a `DataSourceError`,
 * so the UI never has to render a raw runtime message.
 */
export function toDataSourceError(error: unknown): DataSourceError {
  if (isDataSourceError(error)) {
    return error;
  }

  if (error instanceof DOMException && error.name === "AbortError") {
    return new DataSourceError({
      kind: "network",
      message: "Le service de données n'a pas répondu dans le délai imparti.",
      cause: error,
    });
  }

  return new DataSourceError({
    kind: "network",
    message: error instanceof Error ? error.message : undefined,
    cause: error,
  });
}
