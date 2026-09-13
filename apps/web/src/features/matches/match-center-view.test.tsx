process.env.TZ = "UTC";

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
import type { FootballModelPrediction } from "@/types/api";
import { screen, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

function displayedProbability(value: number): string {
  return formatProbability(value).replace(/\u202f/g, " ");
}

async function expectCopiedEnginePercents(
  link: HTMLElement,
  prediction: FootballModelPrediction,
): Promise<void> {
  const card = within(link);
  expect(await card.findByText(displayedProbability(prediction.home_probability))).toBeInTheDocument();
  expect(card.getByText(displayedProbability(prediction.draw_probability))).toBeInTheDocument();
  expect(card.getByText(displayedProbability(prediction.away_probability))).toBeInTheDocument();
  expect(link).not.toHaveTextContent(/Prédiction indisponible/);
}

describe("MatchCenterView", () => {
  beforeEach(() => {
    process.env.TZ = "UTC";
    vi.useFakeTimers({
      now: new Date("2026-09-13T12:00:00.000Z"),
      toFake: ["Date"],
    });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

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

    expect(screen.getByRole("tab", { name: /Toutes/ })).toHaveAttribute("aria-selected", "true");

    const torino = await screen.findByRole("link", { name: /Torino/ });
    const inter = await screen.findByRole("link", { name: /Inter vs/ });
    const lazio = await screen.findByRole("link", { name: /Lazio/ });

    expect(torino).toHaveAttribute("href", `/football/matches/${TORINO_ROMA_MATCH_ID}`);
    expect(inter).toHaveAttribute("href", `/football/matches/${INTER_UDINESE_MATCH_ID}`);
    expect(lazio).toHaveAttribute("href", `/football/matches/${UDINESE_LAZIO_MATCH_ID}`);

    await expectCopiedEnginePercents(torino, torinoRomaFootballPrediction);
    await expectCopiedEnginePercents(inter, interUdineseFootballPrediction);
    await expectCopiedEnginePercents(lazio, udineseLazioFootballPrediction);
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
