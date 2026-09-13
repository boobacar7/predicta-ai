import { MatchCenterView } from "@/features/matches/match-center-view";
import {
  INTER_UDINESE_MATCH_ID,
  TORINO_ROMA_MATCH_ID,
  UDINESE_LAZIO_MATCH_ID,
  interUdineseFootballPrediction,
  torinoRomaFootballPrediction,
  udineseLazioFootballPrediction,
} from "@/data/mock/football-engine";
import { formatProbability } from "@/lib/format/numbers";
import { renderWithProviders } from "@/test/render";
import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

function displayedProbability(value: number): string {
  return formatProbability(value).replace(/\u202f/g, " ");
}

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

  it("loads canonical football predictions for Torino, Inter and Udinese–Lazio", async () => {
    renderWithProviders(<MatchCenterView />);

    expect(await screen.findByRole("link", { name: /Torino/ })).toHaveAttribute(
      "href",
      `/football/matches/${TORINO_ROMA_MATCH_ID}`,
    );
    expect(screen.getByRole("link", { name: /Inter vs/ })).toHaveAttribute(
      "href",
      `/football/matches/${INTER_UDINESE_MATCH_ID}`,
    );
    expect(screen.getByRole("link", { name: /Lazio/ })).toHaveAttribute(
      "href",
      `/football/matches/${UDINESE_LAZIO_MATCH_ID}`,
    );

    expect(
      await screen.findByText(displayedProbability(torinoRomaFootballPrediction.home_probability)),
    ).toBeInTheDocument();
    expect(screen.getByText(displayedProbability(torinoRomaFootballPrediction.draw_probability))).toBeInTheDocument();
    expect(screen.getByText(displayedProbability(torinoRomaFootballPrediction.away_probability))).toBeInTheDocument();
    expect(screen.getByText(displayedProbability(interUdineseFootballPrediction.home_probability))).toBeInTheDocument();
    expect(screen.getByText(displayedProbability(udineseLazioFootballPrediction.home_probability))).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Torino/ })).not.toHaveTextContent(/Prédiction indisponible/);
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
