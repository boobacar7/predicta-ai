import {
  FOOTBALL_PATHS,
  isFootballNavActive,
} from "@/lib/football/routes";

export type NavItem = {
  href: string;
  label: string;
  description: string;
  icon: "layout" | "calendar" | "spark" | "diamond" | "chart" | "activity" | "message" | "shield" | "users" | "user" | "profile";
};

export type NavSection = {
  id: string;
  label: string;
  items: NavItem[];
};

/**
 * Private-beta chrome. Basketball, tennis and undelivered catalogue surfaces
 * stay out of the primary navigation.
 */
export const navSections: NavSection[] = [
  {
    id: "football",
    label: "Football",
    items: [
      {
        href: FOOTBALL_PATHS.dashboard,
        label: "Dashboard",
        description: "Vue d'ensemble des signaux du jour",
        icon: "layout",
      },
      {
        href: FOOTBALL_PATHS.matches,
        label: "Match Center",
        description: "Calendrier, filtres et détails de match",
        icon: "calendar",
      },
      {
        href: FOOTBALL_PATHS.aiPicks,
        label: "AI Picks",
        description: "Opportunités classées par le moteur, jamais des garanties",
        icon: "spark",
      },
      {
        href: FOOTBALL_PATHS.value,
        label: "Value Finder",
        description: "Écarts entre modèle et cotes observées",
        icon: "diamond",
      },
      {
        href: FOOTBALL_PATHS.aiAnalyst,
        label: "AI Analyst",
        description: "Explication football 1X2 à partir du contexte validé",
        icon: "message",
      },
    ],
  },
];

export const profileNavItem: NavItem = {
  href: "/profile",
  label: "Profil",
  description: "Compte, favoris et préférences à venir",
  icon: "profile",
};

export const pageMeta: Record<string, { title: string; eyebrow: string; description: string }> = {
  [FOOTBALL_PATHS.dashboard]: {
    title: "Dashboard",
    eyebrow: "Football · Vue d'ensemble",
    description: "Signaux du jour, fraîcheur des données et performance récente des modèles.",
  },
  [FOOTBALL_PATHS.matches]: {
    title: "Match Center",
    eyebrow: "Football · Calendrier",
    description: "Parcourez les matchs de football par date et compétition.",
  },
  [FOOTBALL_PATHS.aiPicks]: {
    title: "AI Picks",
    eyebrow: "Football · Signaux",
    description:
      "Opportunités statistiques identifiées par le modèle. Ce ne sont pas des conseils de mise.",
  },
  [FOOTBALL_PATHS.value]: {
    title: "Value Finder",
    eyebrow: "Football · Value Engine",
    description: "Comparaison transparente entre probabilités calibrées et cotes observées.",
  },
  [FOOTBALL_PATHS.aiAnalyst]: {
    title: "AI Analyst",
    eyebrow: "Football Intelligence",
    description:
      "Rapport explicatif construit uniquement à partir du contexte validé. Ce n'est pas une recommandation.",
  },
  "/": {
    title: "Dashboard",
    eyebrow: "Football · Vue d'ensemble",
    description: "Signaux du jour, fraîcheur des données et performance récente des modèles.",
  },
  "/matches": {
    title: "Match Center",
    eyebrow: "Football · Calendrier",
    description: "Parcourez les matchs de football par date et compétition.",
  },
  "/ai-picks": {
    title: "AI Picks",
    eyebrow: "Football · Signaux",
    description:
      "Opportunités statistiques identifiées par le modèle. Ce ne sont pas des conseils de mise.",
  },
  "/value-finder": {
    title: "Value Finder",
    eyebrow: "Football · Value Engine",
    description: "Comparaison transparente entre probabilités calibrées et cotes observées.",
  },
  "/analytics": {
    title: "Statistiques",
    eyebrow: "Intelligence",
    description: "Indicateurs disponibles, avec les lacunes explicitement signalées.",
  },
  "/performance": {
    title: "Performance",
    eyebrow: "Modèles",
    description: "Log loss, Brier, calibration et ROI théorique de backtest.",
  },
  "/ai-analyst": {
    title: "AI Analyst",
    eyebrow: "Football Intelligence",
    description:
      "Rapport explicatif construit uniquement à partir du contexte validé. Ce n'est pas une recommandation.",
  },
  "/analyst": {
    title: "AI Analyst",
    eyebrow: "Football Intelligence",
    description: "Synthèse à partir d'un paquet de faits validés. Aucune donnée n'est inventée.",
  },
  "/leagues": {
    title: "Ligues",
    eyebrow: "Catalogue",
    description: "Compétitions fictives du prototype et contexte de saison.",
  },
  "/teams": {
    title: "Équipes",
    eyebrow: "Catalogue",
    description: "Profils d'équipes du jeu de données mock.",
  },
  "/players": {
    title: "Joueurs",
    eyebrow: "Catalogue",
    description: "Joueurs fictifs utilisés pour le prototype tennis et football.",
  },
  "/profile": {
    title: "Profil",
    eyebrow: "Compte",
    description: "Session invite-only. Favoris et tracker arriveront plus tard.",
  },
  "/login": {
    title: "Connexion",
    eyebrow: "Private Beta",
    description: "Accès sur invitation. Les prédictions restent des probabilités, jamais des garanties.",
  },
};

export { isFootballNavActive };
