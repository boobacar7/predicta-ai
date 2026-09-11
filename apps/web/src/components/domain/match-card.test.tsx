import { MatchCard } from "@/components/domain/match-card";
import { MockDataSource } from "@/data/mock/source";
import type { MatchSummary } from "@/types/api";
import { renderWithProviders as render } from "@/test/render";
import { screen } from "@testing-library/react";
import { beforeAll, describe, expect, it } from "vitest";

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

describe("MatchCard", () => {
  it("links to the match detail page", () => {
    const match = matches[0]!;
    render(<MatchCard match={match} />);

    expect(screen.getByRole("link")).toHaveAttribute("href", `/matches/${match.id}`);
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
    const withoutPrediction = findMatch((match) => match.prediction_preview === null);
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

  it("uses no wording that promises an outcome", () => {
    for (const match of matches) {
      const { container, unmount } = render(<MatchCard match={match} />);
      const text = container.textContent ?? "";

      expect(text).not.toMatch(/garanti|sûr|certain|100\s*%|safe bet/i);
      unmount();
    }
  });
});
