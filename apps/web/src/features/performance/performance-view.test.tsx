import { PerformanceView } from "@/features/performance/performance-view";
import { renderWithProviders } from "@/test/render";
import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

describe("PerformanceView", () => {
  it("does not present fb-ens-* as the football candidate model", () => {
    renderWithProviders(<PerformanceView />);

    expect(screen.getByRole("heading", { name: "Performance", level: 1 })).toBeInTheDocument();
    expect(screen.queryByText("fb-ens-2026.08.1")).not.toBeInTheDocument();
    expect(screen.getByText("Modèle candidat")).toBeInTheDocument();
    expect(screen.getByText(/football-elo-v1-candidate/)).toBeInTheDocument();
    expect(screen.getByText(/indisponible/i)).toBeInTheDocument();
  });
});
