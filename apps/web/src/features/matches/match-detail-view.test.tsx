import { MatchDetailView } from "@/features/matches/match-detail-view";
import { renderWithProviders } from "@/test/render";
import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

describe("MatchDetailView historical identity", () => {
  it("renders the structural identity published for an AI Picks match id", async () => {
    renderWithProviders(<MatchDetailView matchId="mth_football-sportmonks-19719892" />);

    expect(await screen.findByText("Lincoln Red Imps vs Inter Club d'Escaldes")).toBeInTheDocument();
    expect(screen.getByText("Champions League")).toBeInTheDocument();
    expect(screen.getByText("Identité archivée")).toBeInTheDocument();
    expect(screen.getByText("Lincoln Red Imps")).toBeInTheDocument();
    expect(screen.getByText("Inter Club d'Escaldes")).toBeInTheDocument();
    expect(screen.getByText("tm_football-sportmonks-10068")).toBeInTheDocument();

    // The payload is structural: those sections must not be invented.
    expect(screen.queryByText("Probabilités calibrées")).not.toBeInTheDocument();
    expect(screen.queryByText("Chronologie")).not.toBeInTheDocument();
    expect(screen.getByText(/identité structurelle archivée/)).toBeInTheDocument();
    const analystLink = screen.getByRole("link", { name: /Ouvrir dans l'AI Analyst/ });
    expect(analystLink).toHaveAttribute("href", "/ai-analyst?match_id=mth_football-sportmonks-19719892");
  });

  it("still renders a projected MatchDetail for catalogue ids", async () => {
    renderWithProviders(<MatchDetailView matchId="mth_northgate_harbor" />);

    expect(await screen.findByRole("heading", { name: /Northgate FC · Harbor Athletic/ })).toBeInTheDocument();
    expect(screen.queryByText("Identité archivée")).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Ouvrir dans l'AI Analyst/ })).not.toBeInTheDocument();
  });
});
