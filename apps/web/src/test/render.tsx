import { TooltipProvider } from "@/components/ui/tooltip";
import { MockScenarioProvider } from "@/data/mock/scenario-context";
import { FiltersProvider } from "@/lib/filters/context";
import { ThemeProvider } from "@/lib/theme/theme-provider";
import type { Theme } from "@/lib/theme/theme";
import { resetThemeStore, setThemeStore } from "@/lib/theme/theme-store";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions, type RenderResult } from "@testing-library/react";
import type { ReactElement, ReactNode } from "react";
import type { MockScenario } from "@/types/api";
import type { SportFilterValue } from "@/lib/filters/context";

/**
 * Renders a component inside the same providers the application shell installs.
 *
 * Components are tested in their real context rather than being reshaped to be
 * testable, and each test gets a fresh query cache so results never leak between
 * cases.
 */

export interface RenderWithProvidersOptions extends Omit<RenderOptions, "wrapper"> {
  sport?: SportFilterValue;
  scenario?: MockScenario;
  theme?: Theme;
}

export function createTestQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
    },
  });
}

export function renderWithProviders(
  ui: ReactElement,
  { sport = "all", scenario = "success", theme = "dark", ...options }: RenderWithProvidersOptions = {},
): RenderResult & { queryClient: QueryClient } {
  resetThemeStore();
  setThemeStore(theme, false);
  const queryClient = createTestQueryClient();

  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <ThemeProvider initialTheme={theme} persist={false}>
          <TooltipProvider>
            <FiltersProvider initialSport={sport}>
              <MockScenarioProvider initialScenario={scenario}>{children}</MockScenarioProvider>
            </FiltersProvider>
          </TooltipProvider>
        </ThemeProvider>
      </QueryClientProvider>
    );
  }

  return { ...render(ui, { wrapper: Wrapper, ...options }), queryClient };
}
