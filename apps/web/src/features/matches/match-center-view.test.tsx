import { MatchCenterView } from "@/features/matches/match-center-view";
import { renderWithProviders } from "@/test/render";
import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

describe("MatchCenterView", () => {
  it("shows no match cards before the first response", () => {
    renderWithProviders(<MatchCenterView />);

    expect(screen.getByRole("heading", { name: "Match Center", level: 1 })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Northgate/ })).not.toBeInTheDocument();
  });

  it("lists football matches and hides basketball and tennis", async () => {
    renderWithProviders(<MatchCenterView />);

    expect(await screen.findByText("Northgate FC")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Match Center", level: 1 })).toBeInTheDocument();
    expect(screen.queryByText(/Helix/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Voss/)).not.toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Toutes/ })).toHaveAttribute("aria-selected", "true");
  });

  it("uses EmptyState when the list is empty", async () => {
    renderWithProviders(<MatchCenterView />, { scenario: "empty" });

    expect(await screen.findByText("Aucun match")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Réessayer" })).not.toBeInTheDocument();
  });

  it("shows an error panel with retry when the read fails", async () => {
    renderWithProviders(<MatchCenterView />, { scenario: "error" });

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Réessayer" })).toBeInTheDocument();
  });
});
