import { UNKNOWN_IDENTITY_LABEL } from "@/lib/format/identity";
import { football1x2Labels } from "@/lib/format/labels";
import {
  formatCount,
  formatPoints,
  formatProbability,
  formatSignedPercent,
} from "@/lib/format/numbers";
import type { FootballAnalystFactor } from "@/types/api";

export const FACTOR_DIRECTION_LABELS = {
  home: "Domicile",
  away: "Extérieur",
  draw: "Nul",
  neutral: "Neutre",
} as const;

export function formatFactorValue(factor: FootballAnalystFactor): string {
  if (factor.value === null) {
    return UNKNOWN_IDENTITY_LABEL;
  }

  if (Number.isNaN(factor.value)) {
    return UNKNOWN_IDENTITY_LABEL;
  }

  switch (factor.type) {
    case "model_probability":
    case "market_probability":
      return formatProbability(factor.value);
    case "edge":
      return formatPoints(factor.value);
    case "ev":
      return formatSignedPercent(factor.value);
    case "data_freshness":
      return `${formatCount(Math.round(factor.value))} s`;
    case "model_status":
      return UNKNOWN_IDENTITY_LABEL;
  }
}

export function selectionSideLabel(selection: "HOME" | "DRAW" | "AWAY" | null | undefined): string {
  if (!selection) {
    return UNKNOWN_IDENTITY_LABEL;
  }

  return football1x2Labels[selection];
}
