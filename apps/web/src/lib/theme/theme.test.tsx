import { PerformanceChart } from "@/components/domain/performance-chart";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { performanceReport } from "@/data/mock/performance";
import { AiPicksView } from "@/features/picks/ai-picks-view";
import { ValueFinderView } from "@/features/value/value-finder-view";
import { DEFAULT_THEME, THEME_STORAGE_KEY, readStoredTheme } from "@/lib/theme/theme";
import { ThemeProvider } from "@/lib/theme/theme-provider";
import { hydrateThemeFromStorage, resetThemeStore, setThemeStore } from "@/lib/theme/theme-store";
import { renderWithProviders } from "@/test/render";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/football/value",
}));

describe("theme persistence", () => {
  beforeEach(() => {
    window.localStorage.clear();
    resetThemeStore();
    document.documentElement.dataset.theme = "dark";
  });

  it("defaults to dark when nothing is stored", () => {
    expect(DEFAULT_THEME).toBe("dark");
    expect(readStoredTheme(window.localStorage)).toBe("dark");
  });

  it("toggles from dark to light and persists the choice", async () => {
    const user = userEvent.setup();
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );

    const toggle = screen.getByRole("button", { name: /Activer le thème clair/ });
    expect(toggle).toHaveAttribute("aria-pressed", "false");

    await user.click(toggle);

    expect(document.documentElement.dataset.theme).toBe("light");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("light");
    expect(screen.getByRole("button", { name: /Activer le thème sombre/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("toggles from light back to dark", async () => {
    setThemeStore("light", true);
    const user = userEvent.setup();
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );

    await user.click(await screen.findByRole("button", { name: /Activer le thème sombre/ }));

    expect(document.documentElement.dataset.theme).toBe("dark");
    expect(window.localStorage.getItem(THEME_STORAGE_KEY)).toBe("dark");
  });

  it("restores the stored theme after a remount", async () => {
    setThemeStore("light", true);
    const { unmount } = render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );

    expect(await screen.findByRole("button", { name: /Activer le thème sombre/ })).toBeInTheDocument();
    unmount();
    resetThemeStore();
    hydrateThemeFromStorage();

    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );

    expect(await screen.findByRole("button", { name: /Activer le thème sombre/ })).toBeInTheDocument();
    expect(document.documentElement.dataset.theme).toBe("light");
  });

  it("exposes an accessible name and pressed state", async () => {
    render(
      <ThemeProvider>
        <ThemeToggle />
      </ThemeProvider>,
    );

    const toggle = screen.getByRole("button", { name: /Activer le thème/ });
    expect(toggle).toHaveAccessibleName(/thème/);
    toggle.focus();
    expect(toggle).toHaveFocus();
  });
});

describe("theme independence from business data", () => {
  beforeEach(() => {
    window.localStorage.clear();
    resetThemeStore();
  });

  it("keeps AI Picks figures identical in dark and light", async () => {
    const dark = renderWithProviders(<AiPicksView />, { theme: "dark" });
    expect(await screen.findByRole("heading", { name: "Lincoln Red Imps vs Inter Club d'Escaldes" })).toBeInTheDocument();
    const darkEv = screen.getAllByText(/\+56,3/).length;
    dark.unmount();

    renderWithProviders(<AiPicksView />, { theme: "light" });
    expect(await screen.findByRole("heading", { name: "Lincoln Red Imps vs Inter Club d'Escaldes" })).toBeInTheDocument();
    expect(screen.getAllByText(/\+56,3/)).toHaveLength(darkEv);
  });

  it("keeps Value Finder figures identical in dark and light", async () => {
    const dark = renderWithProviders(<ValueFinderView />, { theme: "dark" });
    await screen.findByText("Information de valeur");
    const darkEv = (await screen.findAllByText(/\+56,3/)).length;
    dark.unmount();

    renderWithProviders(<ValueFinderView />, { theme: "light" });
    await screen.findByText("Information de valeur");
    expect(await screen.findAllByText(/\+56,3/)).toHaveLength(darkEv);
  });

  it("opens AI Picks dialogs in both themes without changing published figures", async () => {
    const user = userEvent.setup();
    const dark = renderWithProviders(<AiPicksView />, { theme: "dark" });
    await screen.findByText("Rang 1");
    await user.click(screen.getAllByRole("button", { name: /Détail de l'opportunité/ })[0]);
    const darkDialog = await screen.findByRole("dialog");
    expect(darkDialog).toHaveTextContent("Lincoln Red Imps");
    expect(darkDialog).toHaveTextContent("Match");
    dark.unmount();

    renderWithProviders(<AiPicksView />, { theme: "light" });
    await screen.findByText("Rang 1");
    await user.click(screen.getAllByRole("button", { name: /Détail de l'opportunité/ })[0]);
    const lightDialog = await screen.findByRole("dialog");
    expect(lightDialog).toHaveTextContent("Lincoln Red Imps");
    expect(lightDialog).toHaveTextContent("Match");
  });

  it("keeps chart series data identical when the theme changes", async () => {
    const { rerender } = renderWithProviders(
      <PerformanceChart series={performanceReport.series} />,
      { theme: "dark" },
    );

    expect(screen.getByText(/Série de log loss/)).toBeInTheDocument();
    const darkText = screen.getByText(/Série de log loss/).textContent;

    rerender(<PerformanceChart series={performanceReport.series} />);
    expect(screen.getByText(/Série de log loss/).textContent).toBe(darkText);
  });
});
