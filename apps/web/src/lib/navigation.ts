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

export const navSections: NavSection[] = [
  {
    id: "analyse",
    label: "Analyse",
    items: [
      {
        href: "/",
        label: "Dashboard",
        description: "Vue d'ensemble des signaux du jour",
        icon: "layout",
      },
      {
        href: "/matches",
        label: "Match Center",
        description: "Calendrier, filtres et détails de match",
        icon: "calendar",
      },
      {
        href: "/ai-picks",
        label: "AI Picks",
        description: "Opportunités classées par le moteur, jamais des garanties",
        icon: "spark",
      },
      {
        href: "/value-finder",
        label: "Value Finder",
        description: "Écarts entre modèle et cotes observées",
        icon: "diamond",
      },
    ],
  },
  {
    id: "intelligence",
    label: "Intelligence",
    items: [
      {
        href: "/analytics",
        label: "Statistiques",
        description: "Comparaisons et indicateurs disponibles",
        icon: "chart",
      },
      {
        href: "/performance",
        label: "Performance",
        description: "Calibration, log loss et historique",
        icon: "activity",
      },
      {
        href: "/ai-analyst",
        label: "AI Analyst",
        description: "Explication football 1X2 à partir du contexte validé",
        icon: "message",
      },
    ],
  },
  {
    id: "catalogue",
    label: "Catalogue",
    items: [
      {
        href: "/leagues",
        label: "Ligues",
        description: "Compétitions et contextes de saison",
        icon: "shield",
      },
      {
        href: "/teams",
        label: "Équipes",
        description: "Profils et indicateurs d'équipe",
        icon: "users",
      },
      {
        href: "/players",
        label: "Joueurs",
        description: "Profils individuels lorsque disponibles",
        icon: "user",
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
  "/": {
    title: "Dashboard",
    eyebrow: "Vue d'ensemble",
    description: "Signaux du jour, fraîcheur des données et performance récente des modèles.",
  },
  "/matches": {
    title: "Match Center",
    eyebrow: "Calendrier",
    description: "Parcourez les événements par sport, date et compétition.",
  },
  "/ai-picks": {
    title: "AI Picks",
    eyebrow: "Signaux",
    description: "Opportunités statistiques identifiées par le modèle. Ce ne sont pas des conseils de mise.",
  },
  "/value-finder": {
    title: "Value Finder",
    eyebrow: "Value Engine",
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
    eyebrow: "Explication",
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
