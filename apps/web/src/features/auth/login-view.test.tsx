import { LoginView } from "@/features/auth/login-view";
import { AuthSessionProvider } from "@/features/auth/session-context";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/login",
}));

function renderLogin() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        <AuthSessionProvider>{children}</AuthSessionProvider>
      </QueryClientProvider>
    );
  }
  return render(<LoginView />, { wrapper: Wrapper });
}

describe("LoginView", () => {
  it("does not offer a password form when the mock prototype has no API", async () => {
    renderLogin();

    expect(await screen.findByText(/Private Beta/)).toBeInTheDocument();
    expect(screen.getByText(/aucune API n’est configurée/)).toBeInTheDocument();
    expect(screen.queryByLabelText(/Email invité/)).not.toBeInTheDocument();
    expect(window.localStorage.getItem("predicta_session")).toBeNull();
    expect(window.localStorage.getItem("jwt")).toBeNull();
  });
});
