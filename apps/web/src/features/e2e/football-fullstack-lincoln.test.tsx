import { AiAnalystView } from "@/features/ai-analyst/ai-analyst-view";
import { DashboardView } from "@/features/dashboard/dashboard-view";
import { MatchDetailView } from "@/features/matches/match-detail-view";
import { AiPicksView } from "@/features/picks/ai-picks-view";
import { ValueFinderView } from "@/features/value/value-finder-view";
import { renderWithProviders } from "@/test/render";
import { screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const navigation = {
  matchId: "",
  replace: vi.fn(),
};

vi.mock("next/navigation", () => ({
  useSearchParams: () =>
    new URLSearchParams(navigation.matchId ? { match_id: navigation.matchId } : undefined),
  useRouter: () => ({ replace: navigation.replace }),
  usePathname: () => "/e2e",
}));

describe("Lincoln fullstack football journey", () => {
  beforeEach(() => {
    navigation.matchId = "mth_football-sportmonks-19719892";
    navigation.replace.mockReset();
  });

  it("Dashboard reads AI Picks and Value Engine for Lincoln, not fb-ens catalogue math", async () => {
    renderWithProviders(<DashboardView />);

    expect(await screen.findByRole("heading", { name: "Dashboard", level: 1 })).toBeInTheDocument();
    expect(
      await screen.findByRole("heading", { name: "Lincoln Red Imps vs Inter Club d'Escaldes" }),
    ).toBeInTheDocument();
    expect(screen.getAllByText("+56,3 %").length).toBeGreaterThan(0);
    expect(screen.getByText(/ne constitue pas une recommandation/)).toBeInTheDocument();
    expect(screen.getByText(/mth_football-sportmonks-19719892/)).toBeInTheDocument();
    expect(screen.queryByText("fb-ens-2026.08.1")).not.toBeInTheDocument();
    expect(screen.getAllByText(/football-elo-v1-candidate/).length).toBeGreaterThan(0);
  });

  it("Match Details keeps the archived identity and copies football prediction and value", async () => {
    renderWithProviders(<MatchDetailView matchId="mth_football-sportmonks-19719892" />);

    expect(await screen.findByText("Lincoln Red Imps vs Inter Club d'Escaldes")).toBeInTheDocument();
    expect(screen.getByText("Champions League")).toBeInTheDocument();
    expect(screen.getByText("Lincoln Red Imps")).toBeInTheDocument();
    expect(screen.getByText("Inter Club d'Escaldes")).toBeInTheDocument();
    expect(await screen.findByText("Prédiction moteur")).toBeInTheDocument();
    expect(screen.getAllByText("41,7 %").length).toBeGreaterThan(0);
    expect(screen.getByText("Information de valeur")).toBeInTheDocument();
    expect(screen.getByText("-16,7 %")).toBeInTheDocument();
    expect(screen.getByText("+56,3 %")).toBeInTheDocument();
    expect(screen.queryByText("Chronologie")).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Ouvrir dans l'AI Analyst/ })).toHaveAttribute(
      "href",
      "/ai-analyst?match_id=mth_football-sportmonks-19719892",
    );
  });

  it("Value Finder reads GET /football/value for Lincoln", async () => {
    renderWithProviders(<ValueFinderView />);

    expect(await screen.findByRole("heading", { name: "Value Finder", level: 1 })).toBeInTheDocument();
    expect(await screen.findByText("Information de valeur")).toBeInTheDocument();
    expect(screen.getAllByText("Lincoln Red Imps vs Inter Club d'Escaldes").length).toBeGreaterThan(0);
    expect(screen.getByText("-16,7 %")).toBeInTheDocument();
    expect(screen.getByText("+56,3 %")).toBeInTheDocument();
    expect(screen.queryByText("Northgate FC · Harbor Athletic")).not.toBeInTheDocument();
  });

  it("AI Picks ranks the published Lincoln AWAY opportunity first", async () => {
    renderWithProviders(<AiPicksView />);

    expect(await screen.findByText("Rang 1")).toBeInTheDocument();
    expect(
      screen.getAllByRole("heading", { name: "Lincoln Red Imps vs Inter Club d'Escaldes" }).length,
    ).toBeGreaterThan(0);
    expect(screen.getAllByText("31,3 %").length).toBeGreaterThan(0);
    expect(screen.getAllByText("+56,3 %").length).toBeGreaterThan(0);
    expect(screen.getAllByText("predicta-mock-odds-v0.1").length).toBeGreaterThan(0);
    expect(screen.getAllByText("football-elo-v1-candidate").length).toBeGreaterThan(0);
    expect(screen.getByText("Mock data")).toBeInTheDocument();
    expect(screen.getByText("Modèle candidat")).toBeInTheDocument();
  });

  it("AI Analyst copies the same Lincoln favorite, value selection and mock provenance", async () => {
    renderWithProviders(<AiAnalystView />);

    expect(
      await screen.findByRole("heading", { name: "Lincoln Red Imps vs Inter Club d'Escaldes" }),
    ).toBeInTheDocument();
    expect(screen.getByText(/Champions League/)).toBeInTheDocument();
    expect(screen.getAllByText("Favori du modèle · Domicile").length).toBeGreaterThan(0);
    expect(screen.getByText("Valeur détectée · Extérieur")).toBeInTheDocument();
    expect(screen.getAllByText(/41,7/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/-16,7/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("football-elo-v1-candidate").length).toBeGreaterThan(0);
    expect(document.body.textContent ?? "").not.toMatch(/pari recommandé|mise conseillée|safe bet/i);
  });
});
