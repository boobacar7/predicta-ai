import type { Football1x2Selection, FootballValueAnalysis } from "@/types/api";

export type FootballValueSort = "edge" | "ev" | "probability" | "odds" | "selection";

export interface FootballValueRow {
  selection: Football1x2Selection;
  model_probability: number;
  odds: number;
  implied_probability: number;
  no_vig_probability: number;
  edge: number;
  ev: number;
}

/**
 * Copies the three 1X2 rows the Value Engine already published.
 *
 * Display shaping only: no implied probability, no-vig, edge or EV is derived.
 */
export function footballValueRows(analysis: FootballValueAnalysis): FootballValueRow[] {
  return [
    {
      selection: "HOME",
      model_probability: analysis.prediction.home_probability,
      odds: analysis.odds.home_odds,
      implied_probability: analysis.market_probabilities.home.implied_probability,
      no_vig_probability: analysis.market_probabilities.home.no_vig_probability,
      edge: analysis.value.home.edge,
      ev: analysis.value.home.ev,
    },
    {
      selection: "DRAW",
      model_probability: analysis.prediction.draw_probability,
      odds: analysis.odds.draw_odds,
      implied_probability: analysis.market_probabilities.draw.implied_probability,
      no_vig_probability: analysis.market_probabilities.draw.no_vig_probability,
      edge: analysis.value.draw.edge,
      ev: analysis.value.draw.ev,
    },
    {
      selection: "AWAY",
      model_probability: analysis.prediction.away_probability,
      odds: analysis.odds.away_odds,
      implied_probability: analysis.market_probabilities.away.implied_probability,
      no_vig_probability: analysis.market_probabilities.away.no_vig_probability,
      edge: analysis.value.away.edge,
      ev: analysis.value.away.ev,
    },
  ];
}

/** Local visual order of already-published rows. */
export function sortFootballValueRows(
  rows: readonly FootballValueRow[],
  sort: FootballValueSort,
): FootballValueRow[] {
  const sorted = [...rows];

  switch (sort) {
    case "edge":
      return sorted.sort((a, b) => b.edge - a.edge);
    case "ev":
      return sorted.sort((a, b) => b.ev - a.ev);
    case "probability":
      return sorted.sort((a, b) => b.model_probability - a.model_probability);
    case "odds":
      return sorted.sort((a, b) => b.odds - a.odds);
    case "selection":
      return sorted;
  }
}
