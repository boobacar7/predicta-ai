import { DashboardView } from "@/features/dashboard/dashboard-view";
import { renderWithProviders } from "@/test/render";
import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

describe("DashboardView", () => {
  it("does not present fb-ens-* as the football engine", async () => {
    renderWithProviders(<DashboardView />);

    expect(await screen.findByRole("heading", { name: "Dashboard", level: 1 })).toBeInTheDocument();
    expect(screen.queryByText("fb-ens-2026.08.1")).not.toBeInTheDocument();
    expect(screen.getByText("Log loss").parentElement).toHaveTextContent("Indisponible");
    expect(screen.getByText("ROI théorique").parentElement).toHaveTextContent("Indisponible");
  });

  it("loads AI Picks from the football engine", async () => {
    renderWithProviders(<DashboardView />);

    expect(
      await screen.findByRole("heading", { name: "Lincoln Red Imps vs Inter Club d'Escaldes" }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("+56,3 %").length).toBeGreaterThan(0);
  });

  it("loads Value Engine rows for Lincoln without calling them a pick", async () => {
    renderWithProviders(<DashboardView />);

    expect(await screen.findByText(/ne constitue pas une recommandation/)).toBeInTheDocument();
    expect(screen.getByText(/mth_football-sportmonks-19719892/)).toBeInTheDocument();
  });

  it("marks the football model as a candidate", async () => {
    renderWithProviders(<DashboardView />);

    expect(await screen.findByText("Modèle candidat")).toBeInTheDocument();
    expect(screen.getAllByText(/football-elo-v1-candidate/).length).toBeGreaterThan(0);
  });
});
