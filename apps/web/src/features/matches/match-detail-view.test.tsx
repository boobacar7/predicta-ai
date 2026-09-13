import { MatchDetailView } from "@/features/matches/match-detail-view";
import { MockDataSource } from "@/data/mock/source";
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
import { describe, expect, it, vi } from "vitest";

function displayedProbability(value: number): string {
  return formatProbability(value).replace(/\u202f/g, " ");
}

describe("MatchDetailView historical identity", () => {
  it("renders the structural identity published for an AI Picks match id", async () => {
    renderWithProviders(<MatchDetailView matchId="mth_football-sportmonks-19719892" />);

    expect(await screen.findByText("Lincoln Red Imps vs Inter Club d'Escaldes")).toBeInTheDocument();
    expect(screen.getByText("Champions League")).toBeInTheDocument();
    expect(screen.getByText("Identité archivée")).toBeInTheDocument();
    expect(screen.getByText("Lincoln Red Imps")).toBeInTheDocument();
    expect(screen.getByText("Inter Club d'Escaldes")).toBeInTheDocument();
    expect(screen.getByText("tm_football-sportmonks-10068")).toBeInTheDocument();

    expect(await screen.findByText("Prédiction moteur")).toBeInTheDocument();
    expect(screen.getAllByText("41,7 %").length).toBeGreaterThan(0);
    expect(screen.getByText("Information de valeur")).toBeInTheDocument();
    expect(screen.queryByText("Chronologie")).not.toBeInTheDocument();
    expect(screen.getByText(/identité structurelle archivée/)).toBeInTheDocument();
    const analystLink = screen.getByRole("link", { name: /Ouvrir dans l'AI Analyst/ });
    expect(analystLink).toHaveAttribute(
      "href",
      "/football/ai-analyst?match_id=mth_football-sportmonks-19719892",
    );
  });

  it("still renders a projected MatchDetail for catalogue ids", async () => {
    renderWithProviders(<MatchDetailView matchId="mth_northgate_harbor" />);

    expect(await screen.findByRole("heading", { name: /Northgate FC · Harbor Athletic/ })).toBeInTheDocument();
    expect(screen.queryByText("Identité archivée")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Ouvrir dans l'AI Analyst/ })).toHaveAttribute(
      "href",
      "/football/ai-analyst?match_id=mth_northgate_harbor",
    );
  });
});

describe("MatchDetailView catalog engine matches", () => {
  it("loads Torino–Roma from GET /football/predictions instead of the catalogue DTO", async () => {
    renderWithProviders(<MatchDetailView matchId={TORINO_ROMA_MATCH_ID} />);

    expect(await screen.findByRole("heading", { name: /Torino · Roma/ })).toBeInTheDocument();
    expect(await screen.findByText("Prédiction moteur")).toBeInTheDocument();
    expect(screen.getByText(displayedProbability(torinoRomaFootballPrediction.home_probability))).toBeInTheDocument();
    expect(screen.getByText(displayedProbability(torinoRomaFootballPrediction.draw_probability))).toBeInTheDocument();
    expect(screen.getByText(displayedProbability(torinoRomaFootballPrediction.away_probability))).toBeInTheDocument();
    expect(screen.getAllByText(torinoRomaFootballPrediction.model_version).length).toBeGreaterThan(0);
    expect(screen.queryByText(/Prédiction indisponible/)).not.toBeInTheDocument();
    expect(screen.queryByText(/Aucune version de modèle/)).not.toBeInTheDocument();
  });

  it("loads Inter–Udinese from GET /football/predictions", async () => {
    renderWithProviders(<MatchDetailView matchId={INTER_UDINESE_MATCH_ID} />);

    expect(await screen.findByRole("heading", { name: /Inter · Udinese/ })).toBeInTheDocument();
    expect(await screen.findByText("Prédiction moteur")).toBeInTheDocument();
    expect(screen.getByText(displayedProbability(interUdineseFootballPrediction.home_probability))).toBeInTheDocument();
    expect(screen.getByText(displayedProbability(interUdineseFootballPrediction.away_probability))).toBeInTheDocument();
  });

  it("loads Udinese–Lazio from GET /football/predictions", async () => {
    renderWithProviders(<MatchDetailView matchId={UDINESE_LAZIO_MATCH_ID} />);

    expect(await screen.findByRole("heading", { name: /Udinese · Lazio/ })).toBeInTheDocument();
    expect(await screen.findByText("Prédiction moteur")).toBeInTheDocument();
    expect(screen.getByText(displayedProbability(udineseLazioFootballPrediction.home_probability))).toBeInTheDocument();
    expect(screen.getByText(displayedProbability(udineseLazioFootballPrediction.away_probability))).toBeInTheDocument();
  });

  it("does not fetch a pre-match prediction for a finished catalog match", async () => {
    const spy = vi.spyOn(MockDataSource.prototype, "getFootballPrediction");
    renderWithProviders(<MatchDetailView matchId="mth_finished_demo" />);

    expect(await screen.findByRole("heading", { name: /Oakmont City · Silverpark/ })).toBeInTheDocument();
    expect(await screen.findByText(/Le moteur football n'a publié aucune prédiction/)).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });
});


describe("MatchDetailView historical identity", () => {
  it("renders the structural identity published for an AI Picks match id", async () => {
    renderWithProviders(<MatchDetailView matchId="mth_football-sportmonks-19719892" />);

    expect(await screen.findByText("Lincoln Red Imps vs Inter Club d'Escaldes")).toBeInTheDocument();
    expect(screen.getByText("Champions League")).toBeInTheDocument();
    expect(screen.getByText("Identité archivée")).toBeInTheDocument();
    expect(screen.getByText("Lincoln Red Imps")).toBeInTheDocument();
    expect(screen.getByText("Inter Club d'Escaldes")).toBeInTheDocument();
    expect(screen.getByText("tm_football-sportmonks-10068")).toBeInTheDocument();

    expect(await screen.findByText("Prédiction moteur")).toBeInTheDocument();
    expect(screen.getAllByText("41,7 %").length).toBeGreaterThan(0);
    expect(screen.getByText("Information de valeur")).toBeInTheDocument();
    expect(screen.queryByText("Chronologie")).not.toBeInTheDocument();
    expect(screen.getByText(/identité structurelle archivée/)).toBeInTheDocument();
    const analystLink = screen.getByRole("link", { name: /Ouvrir dans l'AI Analyst/ });
    expect(analystLink).toHaveAttribute(
      "href",
      "/football/ai-analyst?match_id=mth_football-sportmonks-19719892",
    );
  });

  it("still renders a projected MatchDetail for catalogue ids", async () => {
    renderWithProviders(<MatchDetailView matchId="mth_northgate_harbor" />);

    expect(await screen.findByRole("heading", { name: /Northgate FC · Harbor Athletic/ })).toBeInTheDocument();
    expect(screen.queryByText("Identité archivée")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Ouvrir dans l'AI Analyst/ })).toHaveAttribute(
      "href",
      "/football/ai-analyst?match_id=mth_northgate_harbor",
    );
  });
});
