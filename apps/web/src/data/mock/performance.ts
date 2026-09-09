import { quality } from "@/data/mock/quality";
import type { Insight, PerformanceReport } from "@/types/api";

const source = "mock.fixtures.v1";

export const insights: Insight[] = [
  {
    id: "ins_1",
    title: "Calibration football stable",
    body: "Sur la fenêtre mock des 30 derniers jours, l'ECE du champion football reste sous 0,04. Ce n'est pas une garantie de résultat.",
    kind: "model",
    href: "/performance",
    quality: quality({ source }),
  },
  {
    id: "ins_2",
    title: "Cotes Silverpark anciennes",
    body: "Le snapshot Atlas pour Silverpark–Westbridge a plus de 8 h. L'edge affiché est marqué stale.",
    kind: "caution",
    href: "/value",
    quality: quality({ source, availability: "stale", freshness: "stale" }),
  },
  {
    id: "ins_3",
    title: "xG live indisponible",
    body: "Le match Riverside–Oakmont n'expose que les tirs. Les xG ne doivent pas être interpolés.",
    kind: "data",
    href: "/matches/mth_riverside_oakmont",
    quality: quality({ source, availability: "partial" }),
  },
];

export const performanceReport: PerformanceReport = {
  summary: {
    model_version: "fb-ens-2026.08.1",
    sport: "football",
    window_label: "Walk-forward 90 jours (mock)",
    accuracy: 0.512,
    log_loss: 0.981,
    brier_score: 0.238,
    ece: 0.031,
    theoretical_roi: 0.027,
    theoretical_max_drawdown: -0.084,
    prediction_count: 640,
    quality: quality({ source, note: "Métriques de backtest fictives, non issues d'un modèle entraîné." }),
  },
  series: [
    { period: "Juin", log_loss: 1.02, brier_score: 0.249, accuracy: 0.49, theoretical_roi: -0.012 },
    { period: "Juil.", log_loss: 0.996, brier_score: 0.241, accuracy: 0.504, theoretical_roi: 0.008 },
    { period: "Août", log_loss: 0.972, brier_score: 0.234, accuracy: 0.518, theoretical_roi: 0.041 },
    { period: "Sept.", log_loss: 0.981, brier_score: 0.238, accuracy: 0.512, theoretical_roi: 0.027 },
  ],
  calibration: [
    { predicted: 0.2, observed: 0.18, count: 72 },
    { predicted: 0.35, observed: 0.33, count: 118 },
    { predicted: 0.5, observed: 0.48, count: 164 },
    { predicted: 0.65, observed: 0.62, count: 141 },
    { predicted: 0.8, observed: 0.77, count: 88 },
  ],
  notes: [
    "Le ROI est théorique : il suppose des mises unitaires au cutoff, sans frais ni limites.",
    "Les splits sont temporels. Aucun tirage aléatoire n'a été utilisé pour ces chiffres mock.",
    "Accuracy seule ne suffit pas à juger le modèle.",
  ],
};
