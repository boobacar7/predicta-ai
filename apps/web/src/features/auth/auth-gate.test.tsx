import { AuthGate, shouldGateAuth } from "@/features/auth/auth-gate";
import { useAuthSession } from "@/features/auth/session-context";
import { buildConfig, getConfig, type WebConfig } from "@/lib/config";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const replace = vi.fn();
let pathname = "/";

vi.mock("next/navigation", () => ({
  usePathname: () => pathname,
  useRouter: () => ({ replace }),
}));

vi.mock("@/lib/config", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@/lib/config")>();
  return { ...actual, getConfig: vi.fn() };
});

vi.mock("@/features/auth/session-context", () => ({
  useAuthSession: vi.fn(),
}));

const stagingHttp = {
  NEXT_PUBLIC_PREDICTA_ENV: "staging",
  NEXT_PUBLIC_PREDICTA_DATA_SOURCE: "http",
  NEXT_PUBLIC_PREDICTA_API_BASE_URL: "https://api.staging.example.test/api/v1",
} as const;

const productionHttp = {
  NEXT_PUBLIC_PREDICTA_ENV: "production",
  NEXT_PUBLIC_PREDICTA_DATA_SOURCE: "http",
  NEXT_PUBLIC_PREDICTA_API_BASE_URL: "https://api.example.test/api/v1",
} as const;

function stagingConfig(bypass: "true" | "false" | undefined): WebConfig {
  return buildConfig({
    ...stagingHttp,
    ...(bypass === undefined ? {} : { NEXT_PUBLIC_PREDICTA_AUTH_BYPASS: bypass }),
  });
}

function productionConfig(bypass: "true" | "false"): WebConfig {
  return buildConfig({ ...productionHttp, NEXT_PUBLIC_PREDICTA_AUTH_BYPASS: bypass });
}

describe("shouldGateAuth", () => {
  it("lets staging + bypass=true through without login", () => {
    expect(shouldGateAuth("/", stagingConfig("true"))).toBe(false);
    expect(shouldGateAuth("/matches", stagingConfig("true"))).toBe(false);
  });

  it("makes production bypass impossible even if the flag is true", () => {
    const config = productionConfig("true");
    expect(config.authBypass).toBe(false);
    expect(shouldGateAuth("/", config)).toBe(true);
  });

  it("keeps AuthGate on when bypass is false", () => {
    expect(shouldGateAuth("/", stagingConfig("false"))).toBe(true);
    expect(shouldGateAuth("/", stagingConfig(undefined))).toBe(true);
    expect(shouldGateAuth("/", productionConfig("false"))).toBe(true);
  });

  it("never gates the login route", () => {
    expect(shouldGateAuth("/login", stagingConfig("false"))).toBe(false);
    expect(shouldGateAuth("/login", productionConfig("true"))).toBe(false);
  });
});

describe("AuthGate", () => {
  beforeEach(() => {
    replace.mockClear();
    pathname = "/";
  });

  it("renders the app on staging bypass without sending the user to /login", () => {
    pathname = "/";
    vi.mocked(getConfig).mockReturnValue(stagingConfig("true"));
    vi.mocked(useAuthSession).mockReturnValue({
      status: "anonymous",
      user: null,
      login: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
    });

    render(
      <AuthGate>
        <p>Dashboard</p>
      </AuthGate>,
    );

    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.queryByText(/Vérification de la session/)).not.toBeInTheDocument();
    expect(replace).not.toHaveBeenCalled();
  });

  it("redirects to login on staging when bypass is off and the session is anonymous", () => {
    pathname = "/matches";
    vi.mocked(getConfig).mockReturnValue(stagingConfig("false"));
    vi.mocked(useAuthSession).mockReturnValue({
      status: "anonymous",
      user: null,
      login: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
    });

    render(
      <AuthGate>
        <p>Dashboard</p>
      </AuthGate>,
    );

    expect(screen.getByText(/Vérification de la session/)).toBeInTheDocument();
    expect(screen.queryByText("Dashboard")).not.toBeInTheDocument();
    expect(replace).toHaveBeenCalledWith("/login?next=%2Fmatches");
  });

  it("still gates production even when the public bypass flag is true", () => {
    pathname = "/";
    vi.mocked(getConfig).mockReturnValue(productionConfig("true"));
    vi.mocked(useAuthSession).mockReturnValue({
      status: "anonymous",
      user: null,
      login: vi.fn(),
      logout: vi.fn(),
      refresh: vi.fn(),
    });

    render(
      <AuthGate>
        <p>Dashboard</p>
      </AuthGate>,
    );

    expect(screen.getByText(/Vérification de la session/)).toBeInTheDocument();
    expect(screen.queryByText("Dashboard")).not.toBeInTheDocument();
    expect(replace).toHaveBeenCalledWith("/login?next=%2F");
  });
});
