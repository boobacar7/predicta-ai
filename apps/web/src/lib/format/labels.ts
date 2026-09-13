import type {
  AiPickExclusionReason,
  AvailabilityStatus,
  ConfidenceLevel,
  Football1x2Selection,
  FootballModelStatus,
  FreshnessLevel,
  MatchStatus,
  SportCode,
} from "@/types/api";

export const sportLabels: Record<SportCode, string> = {
  football: "Football",
  basketball: "Basketball",
  tennis: "Tennis",
};

export const confidenceLabels: Record<ConfidenceLevel, string> = {
  low: "Faible",
  medium: "Moyenne",
  high: "Élevée",
};

export const matchStatusLabels: Record<MatchStatus, string> = {
  scheduled: "À venir",
  live: "En cours",
  finished: "Terminé",
  postponed: "Reporté",
};

export const freshnessLabels: Record<FreshnessLevel, string> = {
  fresh: "Fraîche",
  acceptable: "Acceptable",
  stale: "Ancienne",
};

export const availabilityLabels: Record<AvailabilityStatus, string> = {
  available: "Disponible",
  unavailable: "Indisponible",
  partial: "Partiel",
  stale: "Ancien",
};

/**
 * The engine's 1X2 selections.
 *
 * The side only. Team names live on `AiPick.home_team` / `away_team` and are
 * rendered by the card, so composing them here would duplicate identity in a
 * place that has no way to know whether the archive resolved it.
 */
export const football1x2Labels: Record<Football1x2Selection, string> = {
  HOME: "Domicile",
  DRAW: "Nul",
  AWAY: "Extérieur",
};

export const modelStatusLabels: Record<FootballModelStatus, string> = {
  candidate: "Candidat",
  champion: "Champion",
};

/** Why the engine rejected a selection. One entry per reason in the contract. */
export const exclusionReasonLabels: Record<AiPickExclusionReason, string> = {
  negative_ev: "EV négative",
  negative_edge: "Edge négatif",
  below_minimum_ev: "EV sous le seuil demandé",
  below_minimum_edge: "Edge sous le seuil demandé",
  below_minimum_model_probability: "Probabilité modèle sous le seuil",
  invalid_odds: "Cote invalide",
  incomplete_market: "Marché 1X2 incomplet",
  prediction_unavailable: "Prédiction indisponible",
  pit_unavailable: "Aucun snapshot disponible au cutoff",
  invalid_prediction: "Prédiction non conforme",
  invalid_value: "Résultat Value Engine non conforme",
  stale_odds: "Cote trop ancienne",
};

export function selectionLabel(
  market: string,
  selection: string,
  home: string,
  away: string,
): string {
  if (market === "1x2") {
    if (selection === "home") return home;
    if (selection === "draw") return "Nul";
    if (selection === "away") return away;
  }

  if (market === "moneyline" || market === "winner") {
    if (selection === "home") return home;
    if (selection === "away") return away;
  }

  return selection;
}
