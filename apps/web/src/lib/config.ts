/**
 * Frontend runtime configuration.
 *
 * Validated eagerly with an explicit failure, per docs/development-conventions.md §9.
 * `NEXT_PUBLIC_*` variables are statically inlined by Next.js, so every variable is
 * read through a literal `process.env.X` access rather than a computed key.
 */

/** Where a given resource reads its data from. */
export type DataSourceMode = "mock" | "http";

/**
 * Resources that can be routed independently during the mock -> HTTP migration.
 * One entry per API resource group in docs/architecture.md §16.
 */
export const DATA_RESOURCES = [
  "dashboard",
  "sports",
  "leagues",
  "matches",
  "picks",
  "football_ai_picks",
  "football_ai_analyst",
  "football_predictions",
  "football_value",
  "value",
  "performance",
  "teams",
  "players",
  "analyst",
] as const;

export type DataResource = (typeof DATA_RESOURCES)[number];

/**
 * Deployment target, which is not the same thing as `NODE_ENV`.
 *
 * `NODE_ENV` is `production` for any optimised build, including a local
 * `next build` of the mock prototype. Gating the mock safety rule on it would
 * make the phase-1 prototype impossible to build. This variable describes where
 * the bundle is actually served, so the rule protects real users only.
 */
export type DeploymentEnv = "development" | "staging" | "production";

export interface WebConfig {
  readonly deploymentEnv: DeploymentEnv;
  /** Default mode applied to every resource without an explicit override. */
  readonly defaultMode: DataSourceMode;
  /** Per-resource overrides, enabling endpoint-by-endpoint migration. */
  readonly resourceModes: Readonly<Record<DataResource, DataSourceMode>>;
  /** Base URL of the versioned API, without a trailing slash. */
  readonly apiBaseUrl: string;
  /** Abort budget for a single HTTP read. */
  readonly requestTimeoutMs: number;
}

export class ConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = "ConfigError";
  }
}

function parseMode(value: string, variable: string): DataSourceMode {
  if (value === "mock" || value === "http") {
    return value;
  }

  throw new ConfigError(`Invalid ${variable} "${value}". Expected "mock" or "http".`);
}

/**
 * Parses a comma-separated list of resources that should bypass the default mode.
 * Example: `NEXT_PUBLIC_PREDICTA_HTTP_RESOURCES=matches,performance`.
 */
function parseResourceList(raw: string | undefined, variable: string): DataResource[] {
  if (!raw?.trim()) {
    return [];
  }

  return raw.split(",").map((entry) => {
    const resource = entry.trim();

    if (!isDataResource(resource)) {
      throw new ConfigError(
        `Invalid resource "${resource}" in ${variable}. Expected one of: ${DATA_RESOURCES.join(", ")}.`,
      );
    }

    return resource;
  });
}

function isDataResource(value: string): value is DataResource {
  return (DATA_RESOURCES as readonly string[]).includes(value);
}

function parseTimeout(raw: string | undefined): number {
  if (!raw?.trim()) {
    return 10_000;
  }

  const parsed = Number(raw);

  if (!Number.isFinite(parsed) || parsed <= 0) {
    throw new ConfigError(
      `Invalid NEXT_PUBLIC_PREDICTA_REQUEST_TIMEOUT_MS "${raw}". Expected a positive number of milliseconds.`,
    );
  }

  return parsed;
}

const DEPLOYMENT_ENVS: readonly DeploymentEnv[] = ["development", "staging", "production"];

function parseDeploymentEnv(value: string): DeploymentEnv {
  if ((DEPLOYMENT_ENVS as readonly string[]).includes(value)) {
    return value as DeploymentEnv;
  }

  throw new ConfigError(
    `Invalid NEXT_PUBLIC_PREDICTA_ENV "${value}". Expected one of: ${DEPLOYMENT_ENVS.join(", ")}.`,
  );
}

export type EnvRecord = Readonly<Record<string, string | undefined>>;

export function buildConfig(env: EnvRecord): WebConfig {
  const deploymentEnv = parseDeploymentEnv(env.NEXT_PUBLIC_PREDICTA_ENV ?? "development");
  const defaultMode = parseMode(
    env.NEXT_PUBLIC_PREDICTA_DATA_SOURCE ?? "mock",
    "NEXT_PUBLIC_PREDICTA_DATA_SOURCE",
  );
  const allowMockInProd = env.NEXT_PUBLIC_PREDICTA_ALLOW_MOCK_IN_PROD === "true";
  const httpResources = parseResourceList(
    env.NEXT_PUBLIC_PREDICTA_HTTP_RESOURCES,
    "NEXT_PUBLIC_PREDICTA_HTTP_RESOURCES",
  );
  const mockResources = parseResourceList(
    env.NEXT_PUBLIC_PREDICTA_MOCK_RESOURCES,
    "NEXT_PUBLIC_PREDICTA_MOCK_RESOURCES",
  );

  const overlap = httpResources.filter((resource) => mockResources.includes(resource));
  if (overlap.length > 0) {
    throw new ConfigError(
      `Resources listed in both NEXT_PUBLIC_PREDICTA_HTTP_RESOURCES and NEXT_PUBLIC_PREDICTA_MOCK_RESOURCES: ${overlap.join(", ")}.`,
    );
  }

  const resourceModes = Object.fromEntries(
    DATA_RESOURCES.map((resource) => {
      if (httpResources.includes(resource)) return [resource, "http"] as const;
      if (mockResources.includes(resource)) return [resource, "mock"] as const;
      return [resource, defaultMode] as const;
    }),
  ) as Record<DataResource, DataSourceMode>;

  const usesMock = Object.values(resourceModes).includes("mock");

  if (deploymentEnv === "production" && usesMock && !allowMockInProd) {
    throw new ConfigError(
      "Mock fixtures are blocked in production. Route every resource to http, or set NEXT_PUBLIC_PREDICTA_ALLOW_MOCK_IN_PROD=true for a deliberate demo deployment.",
    );
  }

  const usesHttp = Object.values(resourceModes).includes("http");
  const apiBaseUrl = (env.NEXT_PUBLIC_PREDICTA_API_BASE_URL ?? "").replace(/\/+$/, "");

  if (usesHttp && !apiBaseUrl) {
    throw new ConfigError(
      "NEXT_PUBLIC_PREDICTA_API_BASE_URL is required when any resource reads from http.",
    );
  }

  return {
    deploymentEnv,
    defaultMode,
    resourceModes,
    apiBaseUrl,
    requestTimeoutMs: parseTimeout(env.NEXT_PUBLIC_PREDICTA_REQUEST_TIMEOUT_MS),
  };
}

let cached: WebConfig | undefined;

export function getConfig(): WebConfig {
  cached ??= buildConfig({
    NEXT_PUBLIC_PREDICTA_ENV: process.env.NEXT_PUBLIC_PREDICTA_ENV,
    NEXT_PUBLIC_PREDICTA_DATA_SOURCE: process.env.NEXT_PUBLIC_PREDICTA_DATA_SOURCE,
    NEXT_PUBLIC_PREDICTA_ALLOW_MOCK_IN_PROD: process.env.NEXT_PUBLIC_PREDICTA_ALLOW_MOCK_IN_PROD,
    NEXT_PUBLIC_PREDICTA_HTTP_RESOURCES: process.env.NEXT_PUBLIC_PREDICTA_HTTP_RESOURCES,
    NEXT_PUBLIC_PREDICTA_MOCK_RESOURCES: process.env.NEXT_PUBLIC_PREDICTA_MOCK_RESOURCES,
    NEXT_PUBLIC_PREDICTA_API_BASE_URL: process.env.NEXT_PUBLIC_PREDICTA_API_BASE_URL,
    NEXT_PUBLIC_PREDICTA_REQUEST_TIMEOUT_MS: process.env.NEXT_PUBLIC_PREDICTA_REQUEST_TIMEOUT_MS,
  });

  return cached;
}

/** Resolved routing of the whole app, without constructing a data source. */
export function getDataSourceKind(): "mock" | "http" | "hybrid" {
  const modes = Object.values(getConfig().resourceModes);
  if (modes.every((mode) => mode === "http")) return "http";
  if (modes.every((mode) => mode === "mock")) return "mock";
  return "hybrid";
}

/** Test seam: forces the next `getConfig()` call to re-read the environment. */
export function resetConfigCache(): void {
  cached = undefined;
}

export function getResourceMode(resource: DataResource): DataSourceMode {
  return getConfig().resourceModes[resource];
}
