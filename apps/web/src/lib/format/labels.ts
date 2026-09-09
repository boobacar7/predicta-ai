import type {
  AvailabilityStatus,
  ConfidenceLevel,
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

export const availabilityLabels: Record<AvailabilityStatus, string> = {
  available: "Disponible",
  unavailable: "Indisponible",
  partial: "Partiel",
  stale: "Ancien",
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
