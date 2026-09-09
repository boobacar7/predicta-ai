import { isoMinutesFromNow } from "@/data/mock/clock";
import { matches, toSummary } from "@/data/mock/matches";
import { quality } from "@/data/mock/quality";
import type { Pick, ValueOpportunity } from "@/types/api";

const source = "mock.fixtures.v1";

function matchById(id: string) {
  const found = matches.find((item) => item.id === id);
  if (!found) throw new Error(`Unknown match ${id}`);
  return found;
}

export const picks: Pick[] = [
  {
    id: "pick_northgate_home",
    match: toSummary(matchById("mth_northgate_harbor")),
    market: "1x2",
    selection: "home",
    selection_label: "Northgate FC",
    calibrated_probability: 0.47,
    confidence: "high",
    rationale:
      "Le pick repose sur la probabilité calibrée 47 % pour Northgate, supérieure au seuil interne de publication. Ce n'est pas une recommandation de mise.",
    criteria: "Probabilité calibrée ≥ 45 %, confiance élevée, cutoff respecté.",
    model_version: "fb-ens-2026.08.1",
    published_at: isoMinutesFromNow(-80),
    quality: quality({ source, observed_at: isoMinutesFromNow(-80) }),
  },
  {
    id: "pick_voss",
    match: toSummary(matchById("mth_voss_elian")),
    market: "winner",
    selection: "home",
    selection_label: "Lena Voss",
    calibrated_probability: 0.61,
    confidence: "high",
    rationale:
      "Signal surface dure : Elo dur mock en faveur de Voss. Les blessures ne sont pas dans le fact pack.",
    criteria: "Confiance élevée et marché binaire tennis.",
    model_version: "tn-selo-2026.05.1",
    published_at: isoMinutesFromNow(-70),
    quality: quality({ source, observed_at: isoMinutesFromNow(-70) }),
  },
  {
    id: "pick_helix",
    match: toSummary(matchById("mth_helix_meridian")),
    market: "moneyline",
    selection: "home",
    selection_label: "Helix City",
    calibrated_probability: 0.56,
    confidence: "medium",
    rationale:
      "Probabilité calibrée 56 % pour Helix. La disponibilité des joueurs est indisponible : le pick reste un signal de modèle, pas une certitude.",
    criteria: "Confiance moyenne acceptée si le marché est couvert et le cutoff valide.",
    model_version: "bb-elo-2026.06.2",
    published_at: isoMinutesFromNow(-50),
    quality: quality({ source, observed_at: isoMinutesFromNow(-50) }),
  },
];

export const valueOpportunities: ValueOpportunity[] = [
  {
    id: "val_helix_away",
    match: toSummary(matchById("mth_helix_meridian")),
    market: "moneyline",
    selection: "away",
    selection_label: "Meridian",
    calibrated_probability: 0.44,
    decimal_odds: 2.18,
    implied_probability_raw: 1 / 2.18,
    no_vig_probability: (1 / 2.18) / (1 / 1.72 + 1 / 2.18),
    overround: 1 / 1.72 + 1 / 2.18 - 1,
    edge_raw: 0.44 - 1 / 2.18,
    edge_no_vig: 0.44 - (1 / 2.18) / (1 / 1.72 + 1 / 2.18),
    expected_value: 0.44 * 2.18 - 1,
    formula_version: "value-engine-0.1",
    odds_observed_at: isoMinutesFromNow(-25),
    prediction_cutoff_at: isoMinutesFromNow(-180),
    quality: quality({ source, observed_at: isoMinutesFromNow(-25) }),
  },
  {
    id: "val_northgate_home",
    match: toSummary(matchById("mth_northgate_harbor")),
    market: "1x2",
    selection: "home",
    selection_label: "Northgate FC",
    calibrated_probability: 0.47,
    decimal_odds: 2.2,
    implied_probability_raw: 1 / 2.2,
    no_vig_probability: (1 / 2.2) / (1 / 2.2 + 1 / 3.4 + 1 / 3.5),
    overround: 1 / 2.2 + 1 / 3.4 + 1 / 3.5 - 1,
    edge_raw: 0.47 - 1 / 2.2,
    edge_no_vig: 0.47 - (1 / 2.2) / (1 / 2.2 + 1 / 3.4 + 1 / 3.5),
    expected_value: 0.47 * 2.2 - 1,
    formula_version: "value-engine-0.1",
    odds_observed_at: isoMinutesFromNow(-12),
    prediction_cutoff_at: isoMinutesFromNow(-90),
    quality: quality({ source, observed_at: isoMinutesFromNow(-12) }),
  },
  {
    id: "val_silverpark_stale",
    match: toSummary(matchById("mth_silverpark_westbridge")),
    market: "1x2",
    selection: "home",
    selection_label: "Silverpark",
    calibrated_probability: 0.43,
    decimal_odds: 2.05,
    implied_probability_raw: 1 / 2.05,
    no_vig_probability: (1 / 2.05) / (1 / 2.05 + 1 / 3.45 + 1 / 3.8),
    overround: 1 / 2.05 + 1 / 3.45 + 1 / 3.8 - 1,
    edge_raw: 0.43 - 1 / 2.05,
    edge_no_vig: 0.43 - (1 / 2.05) / (1 / 2.05 + 1 / 3.45 + 1 / 3.8),
    expected_value: 0.43 * 2.05 - 1,
    formula_version: "value-engine-0.1",
    odds_observed_at: isoMinutesFromNow(-480),
    prediction_cutoff_at: isoMinutesFromNow(-360),
    quality: quality({
      source,
      availability: "stale",
      freshness: "stale",
      observed_at: isoMinutesFromNow(-480),
      note: "Cote stale : l'écart affiché n'est pas actionnable.",
    }),
  },
];
