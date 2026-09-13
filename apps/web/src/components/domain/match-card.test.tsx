import { MatchCard } from "@/components/domain/match-card";
import { MockDataSource } from "@/data/mock/source";
import {
  engineCatalogSummaries,
  withMatchStatus,
} from "@/data/mock/engine-catalog-matches";
import {
  INTER_UDINESE_MATCH_ID,
  TORINO_ROMA_MATCH_ID,
  UDINESE_LAZIO_MATCH_ID,
  interUdineseFootballPrediction,
  torinoRomaFootballPrediction,
  udineseLazioFootballPrediction,
} from "@/data/mock/football-engine";
import { formatProbability } from "@/lib/format/numbers";
import type { FootballModelPrediction, MatchSummary } from "@/types/api";
import { renderWithProviders as render } from "@/test/render";
import { screen } from "@testing-library/react";
import { beforeAll, describe, expect, it, vi } from "vitest";

function displayedProbability(value: number): string {
  return formatProbability(value).replace(/\u202f/g, " ");
}

let matches: MatchSummary[];

beforeAll(async () => {
  const result = await new MockDataSource({ latencyMs: 0 }).getMatches();
  matches = result.data.items;
});

function findMatch(predicate: (match: MatchSummary) => boolean): MatchSummary {
  const found = matches.find(predicate);
  if (!found) throw new Error("No fixture satisfies this test's precondition.");
  return found;
}

function catalogMatch(id: string): MatchSummary {
  const found = engineCatalogSummaries.find((match) => match.id === id);
  if (!found) throw new Error(`Missing catalog fixture ${id}`);
  return found;
}

async function expectEngineProbabilities(prediction: FootballModelPrediction) {
  expect(await screen.findByText(displayedProbability(prediction.home_probability))).toBeInTheDocument();
  expect(screen.getByText(displayedProbability(prediction.draw_probability))).toBeInTheDocument();
  expect(screen.getByText(displayedProbability(prediction.away_probability))).toBeInTheDocument();
  expect(screen.getByText(prediction.model_version)).toBeInTheDocument();
  expect(screen.queryByText(/Prédiction indisponible/)).not.toBeInTheDocument();
}

describe("MatchCard", () => {
  it("links to the match detail page", () => {
    const match = matches[0]!;
    render(<MatchCard match={match} />);

    expect(screen.getByRole("link")).toHaveAttribute("href", `/football/matches/${match.id}`);
  });

  it("names both teams and the competition", () => {
    const match = matches[0]!;
    render(<MatchCard match={match} />);

    // The name appears both as the crest label and as the visible team name.
    expect(screen.getAllByText(match.home.name).length).toBeGreaterThan(0);
    expect(screen.getAllByText(match.away.name).length).toBeGreaterThan(0);
    expect(screen.getByText(new RegExp(match.league.name))).toBeInTheDocument();
  });

  it("shows a score only once a match has started", () => {
    const scheduled = findMatch((match) => match.status === "scheduled");
    render(<MatchCard match={scheduled} />);

    expect(screen.getByText("vs")).toBeInTheDocument();
    expect(screen.queryByText("–", { exact: false })).not.toBeInTheDocument();
  });

  /**
   * A match without a published prediction must say so. Rendering a blank slot
   * or a placeholder probability would imply a model output that does not exist.
   */
  it("states when no prediction is published instead of leaving a blank slot", () => {
    const withoutPrediction = findMatch((match) => match.prediction_preview === null && match.status === "finished");
    render(<MatchCard match={withoutPrediction} />);

    expect(screen.getByText(/Prédiction indisponible/)).toBeInTheDocument();
  });

  /**
   * Catalogue football matches still carry a prototype model version. That
   * version must be labelled as prototype, never shown as a live engine output.
   */
  it("labels a catalogue fb-ens prediction as prototype instead of a live probability", () => {
    const withPrediction = findMatch((match) => match.prediction_preview !== null);
    render(<MatchCard match={withPrediction} />);

    expect(screen.getByText("Prototype")).toBeInTheDocument();
    expect(
      screen.getByText(new RegExp(withPrediction.prediction_preview!.model_version)),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Tête/)).not.toBeInTheDocument();
  });

  it("copies Torino–Roma probabilities from GET /football/predictions", async () => {
    render(<MatchCard match={catalogMatch(TORINO_ROMA_MATCH_ID)} />);

    expect(screen.getAllByText("Torino").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Roma").length).toBeGreaterThan(0);
    await expectEngineProbabilities(torinoRomaFootballPrediction);
  });

  it("copies Inter–Udinese probabilities from GET /football/predictions", async () => {
    render(<MatchCard match={catalogMatch(INTER_UDINESE_MATCH_ID)} />);

    expect(screen.getAllByText("Inter").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Udinese").length).toBeGreaterThan(0);
    await expectEngineProbabilities(interUdineseFootballPrediction);
  });

  it("copies Udinese–Lazio probabilities from GET /football/predictions", async () => {
    render(<MatchCard match={catalogMatch(UDINESE_LAZIO_MATCH_ID)} />);

    expect(screen.getAllByText("Udinese").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Lazio").length).toBeGreaterThan(0);
    await expectEngineProbabilities(udineseLazioFootballPrediction);
  });

  it("does not fetch a pre-match prediction for a finished match", async () => {
    const spy = vi.spyOn(MockDataSource.prototype, "getFootballPrediction");
    render(<MatchCard match={withMatchStatus(catalogMatch(TORINO_ROMA_MATCH_ID), "finished")} />);

    expect(await screen.findByText(/Prédiction indisponible/)).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });

  it("shows a loading state before the engine answers", () => {
    render(<MatchCard match={catalogMatch(TORINO_ROMA_MATCH_ID)} />);

    expect(screen.getByLabelText("Chargement de la prédiction")).toBeInTheDocument();
    expect(screen.queryByText(displayedProbability(torinoRomaFootballPrediction.home_probability))).not.toBeInTheDocument();
  });

  it("uses no wording that promises an outcome", async () => {
    for (const match of matches) {
      const { container, unmount } = render(<MatchCard match={match} />);
      const text = container.textContent ?? "";

      expect(text).not.toMatch(/garanti|sûr|certain|100\s*%|safe bet/i);
      unmount();
    }
  });
});
