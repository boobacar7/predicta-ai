import { ConfigError, DATA_RESOURCES, buildConfig, type EnvRecord } from "@/lib/config";
import { describe, expect, it } from "vitest";

const base: EnvRecord = {
  NEXT_PUBLIC_PREDICTA_ENV: "development",
  NEXT_PUBLIC_PREDICTA_DATA_SOURCE: "mock",
};

describe("default routing", () => {
  it("routes every resource to the default mode", () => {
    const config = buildConfig(base);

    expect(Object.values(config.resourceModes).every((mode) => mode === "mock")).toBe(true);
    expect(Object.keys(config.resourceModes)).toHaveLength(DATA_RESOURCES.length);
  });

  it("defaults to mock when no mode is provided", () => {
    expect(buildConfig({}).defaultMode).toBe("mock");
  });

  it("rejects an unknown mode", () => {
    expect(() =>
      buildConfig({ ...base, NEXT_PUBLIC_PREDICTA_DATA_SOURCE: "grpc" }),
    ).toThrow(ConfigError);
  });
});

describe("per-resource overrides", () => {
  it("moves individual resources to http while the rest stay on fixtures", () => {
    const config = buildConfig({
      ...base,
      NEXT_PUBLIC_PREDICTA_HTTP_RESOURCES: "matches, performance",
      NEXT_PUBLIC_PREDICTA_API_BASE_URL: "http://localhost:8000/api/v1",
    });

    expect(config.resourceModes.matches).toBe("http");
    expect(config.resourceModes.performance).toBe("http");
    expect(config.resourceModes.picks).toBe("mock");
  });

  it("keeps named resources on fixtures when the default is http", () => {
    const config = buildConfig({
      ...base,
      NEXT_PUBLIC_PREDICTA_DATA_SOURCE: "http",
      NEXT_PUBLIC_PREDICTA_MOCK_RESOURCES: "analyst",
      NEXT_PUBLIC_PREDICTA_API_BASE_URL: "http://localhost:8000/api/v1",
    });

    expect(config.resourceModes.analyst).toBe("mock");
    expect(config.resourceModes.matches).toBe("http");
  });

  it("rejects an unknown resource name", () => {
    expect(() =>
      buildConfig({ ...base, NEXT_PUBLIC_PREDICTA_HTTP_RESOURCES: "matches,odds" }),
    ).toThrow(/Invalid resource "odds"/);
  });

  it("rejects a resource listed as both http and mock", () => {
    expect(() =>
      buildConfig({
        ...base,
        NEXT_PUBLIC_PREDICTA_HTTP_RESOURCES: "matches",
        NEXT_PUBLIC_PREDICTA_MOCK_RESOURCES: "matches",
      }),
    ).toThrow(/listed in both/);
  });
});

describe("api base url", () => {
  it("is required as soon as a resource reads over http", () => {
    expect(() =>
      buildConfig({ ...base, NEXT_PUBLIC_PREDICTA_HTTP_RESOURCES: "matches" }),
    ).toThrow(/NEXT_PUBLIC_PREDICTA_API_BASE_URL is required/);
  });

  it("strips a trailing slash so path joins stay predictable", () => {
    const config = buildConfig({
      ...base,
      NEXT_PUBLIC_PREDICTA_DATA_SOURCE: "http",
      NEXT_PUBLIC_PREDICTA_API_BASE_URL: "http://localhost:8000/api/v1/",
    });

    expect(config.apiBaseUrl).toBe("http://localhost:8000/api/v1");
  });
});

describe("mock fixtures must not reach real users", () => {
  it("refuses mock data on a staging deployment", () => {
    expect(() => buildConfig({ ...base, NEXT_PUBLIC_PREDICTA_ENV: "staging" })).toThrow(
      /blocked in staging/,
    );
  });

  it("refuses a staging hybrid build even with the production mock flag", () => {
    expect(() =>
      buildConfig({
        NEXT_PUBLIC_PREDICTA_ENV: "staging",
        NEXT_PUBLIC_PREDICTA_DATA_SOURCE: "http",
        NEXT_PUBLIC_PREDICTA_MOCK_RESOURCES: "analyst",
        NEXT_PUBLIC_PREDICTA_API_BASE_URL: "https://api.staging.example.test/api/v1",
        NEXT_PUBLIC_PREDICTA_ALLOW_MOCK_IN_PROD: "true",
      }),
    ).toThrow(/blocked in staging/);
  });

  it("allows a staging build once every resource reads from the api", () => {
    const config = buildConfig({
      NEXT_PUBLIC_PREDICTA_ENV: "staging",
      NEXT_PUBLIC_PREDICTA_DATA_SOURCE: "http",
      NEXT_PUBLIC_PREDICTA_API_BASE_URL: "https://api.staging.example.test/api/v1",
    });

    expect(config.resourceModes.matches).toBe("http");
  });

  it("refuses mock data on a production deployment", () => {
    expect(() =>
      buildConfig({ ...base, NEXT_PUBLIC_PREDICTA_ENV: "production" }),
    ).toThrow(/blocked in production/);
  });

  it("refuses a hybrid build on production when any resource is still mocked", () => {
    expect(() =>
      buildConfig({
        NEXT_PUBLIC_PREDICTA_ENV: "production",
        NEXT_PUBLIC_PREDICTA_DATA_SOURCE: "http",
        NEXT_PUBLIC_PREDICTA_MOCK_RESOURCES: "analyst",
        NEXT_PUBLIC_PREDICTA_API_BASE_URL: "https://api.example.test/api/v1",
      }),
    ).toThrow(/blocked in production/);
  });

  it("allows a production build once every resource reads from the api", () => {
    const config = buildConfig({
      NEXT_PUBLIC_PREDICTA_ENV: "production",
      NEXT_PUBLIC_PREDICTA_DATA_SOURCE: "http",
      NEXT_PUBLIC_PREDICTA_API_BASE_URL: "https://api.example.test/api/v1",
    });

    expect(config.resourceModes.matches).toBe("http");
  });

  it("allows a deliberate mock demo behind the explicit flag", () => {
    const config = buildConfig({
      ...base,
      NEXT_PUBLIC_PREDICTA_ENV: "production",
      NEXT_PUBLIC_PREDICTA_ALLOW_MOCK_IN_PROD: "true",
    });

    expect(config.defaultMode).toBe("mock");
  });

  /**
   * A local `next build` runs with NODE_ENV=production. The guard must not fire
   * there, otherwise the phase-1 prototype cannot be built at all.
   */
  it("does not fire for a development deployment", () => {
    expect(() => buildConfig(base)).not.toThrow();
  });
});

describe("request timeout", () => {
  it("defaults CSRF cookie and header names for the opaque-session client", () => {
    const config = buildConfig(base);
    expect(config.csrfCookieName).toBe("predicta_csrf");
    expect(config.csrfHeaderName).toBe("X-CSRF-Token");
  });

  it("falls back to a bounded default", () => {
    expect(buildConfig(base).requestTimeoutMs).toBe(10_000);
  });

  it("rejects a non-positive timeout", () => {
    expect(() =>
      buildConfig({ ...base, NEXT_PUBLIC_PREDICTA_REQUEST_TIMEOUT_MS: "0" }),
    ).toThrow(ConfigError);
  });
});
