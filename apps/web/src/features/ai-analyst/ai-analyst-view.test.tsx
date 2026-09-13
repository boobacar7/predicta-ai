import { AiAnalystView } from "@/features/ai-analyst/ai-analyst-view";
import {
  ANALYST_INVALID_KICKOFF_ID,
  ANALYST_MISSING_FACTORS_ID,
  ANALYST_MISSING_IDENTITY_ID,
  ANALYST_MISSING_VALUE_ID,
  LINCOLN_ANALYST_MATCH_ID,
} from "@/data/mock/ai-analyst";
import { renderWithProviders } from "@/test/render";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

const navigation = {
  matchId: "",
  replace: vi.fn(),
};

vi.mock("next/navigation", () => ({
  useSearchParams: () =>
    new URLSearchParams(navigation.matchId ? { match_id: navigation.matchId } : undefined),
  useRouter: () => ({ replace: navigation.replace }),
  usePathname: () => "/football/ai-analyst",
}));

async function renderPage(
  options: Parameters<typeof renderWithProviders>[1] & { matchId?: string } = {},
) {
  navigation.matchId = options.matchId ?? "";
  const view = renderWithProviders(<AiAnalystView />, options);
  await screen.findByRole("heading", { name: "AI Analyst", level: 1 });
  return view;
}

describe("AiAnalystView", () => {
  beforeEach(() => {
    navigation.matchId = "";
    navigation.replace.mockReset();
  });

  it("shows no figure before the first response resolves", () => {
    renderWithProviders(<AiAnalystView />);

    expect(screen.queryByText("Favori du modèle · Domicile")).not.toBeInTheDocument();
    expect(document.querySelectorAll("dd")).toHaveLength(0);
  });

  it("renders the Lincoln report with published probabilities", async () => {
    await renderPage();

    expect(await screen.findByRole("heading", { name: "Lincoln Red Imps vs Inter Club d'Escaldes" })).toBeInTheDocument();
    expect(screen.getByText(/Champions League/)).toBeInTheDocument();
    expect(screen.getAllByText(/41,7/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/27,1/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/31,3/).length).toBeGreaterThan(0);
  });

  it("shows the backend model favorite without recomputing it", async () => {
    await renderPage();

    expect(await screen.findAllByText("Favori du modèle · Domicile")).not.toHaveLength(0);
    expect(screen.getByText(/Issue à la plus haute probabilité modèle/)).toBeInTheDocument();
  });

  it("keeps the detected value distinct from the model favorite", async () => {
    await renderPage();

    expect(await screen.findByText("Valeur détectée · Extérieur")).toBeInTheDocument();
    expect(screen.getAllByText(/-16,7/).length).toBeGreaterThan(0);
    expect(screen.getByText(/ne constitue pas une recommandation/)).toBeInTheDocument();
  });

  it("never presents the away side as a pick or a recommendation", async () => {
    await renderPage();

    await screen.findByText("Valeur détectée · Extérieur");
    const body = document.body.textContent ?? "";

    for (const forbidden of ["pari recommandé", "pick", "bet", "mise conseillée", "garanti", "100 %"]) {
      expect(body.toLowerCase()).not.toContain(forbidden);
    }
  });

  it("marks the model as a candidate and never claims high confidence", async () => {
    await renderPage();

    expect(await screen.findByText("Modèle candidat")).toBeInTheDocument();
    expect(screen.getAllByText("football-elo-v1-candidate").length).toBeGreaterThan(0);
    expect(screen.getByLabelText("Confiance : Moyenne")).toBeInTheDocument();
    expect(screen.queryByLabelText("Confiance : Élevée")).not.toBeInTheDocument();
    expect(screen.queryByText("Production")).not.toBeInTheDocument();
    expect(screen.queryByText("Official")).not.toBeInTheDocument();
    expect(screen.queryByText("Guaranteed")).not.toBeInTheDocument();
  });

  it("warns that the payload is mock from data_mode, not from the environment", async () => {
    await renderPage();

    expect(await screen.findByText("Mock data")).toBeInTheDocument();
  });

  it("states that identity is unavailable when both teams are missing", async () => {
    await renderPage({ matchId: ANALYST_MISSING_IDENTITY_ID });

    expect(await screen.findByRole("heading", { name: "Information indisponible vs Information indisponible" })).toBeInTheDocument();
    const body = document.body.textContent ?? "";
    expect(body).not.toContain("null");
    expect(body).not.toContain("undefined");
    expect(body).not.toContain("NaN");
  });

  it("states that value information is unavailable when the engine published none", async () => {
    await renderPage({ matchId: ANALYST_MISSING_VALUE_ID });

    expect((await screen.findAllByText(/aucune analyse de valeur n'est publiée/i)).length).toBeGreaterThan(0);
    expect(screen.getByText("Valeur détectée · Information indisponible")).toBeInTheDocument();
  });

  it("states that key factors are unavailable when the list is empty", async () => {
    await renderPage({ matchId: ANALYST_MISSING_FACTORS_ID });

    expect(await screen.findByRole("heading", { name: "Key Factors" })).toBeInTheDocument();
    expect(screen.getAllByText("Information indisponible").length).toBeGreaterThan(0);
  });

  it("labels an unparseable kickoff instead of rendering Invalid Date", async () => {
    await renderPage({ matchId: ANALYST_INVALID_KICKOFF_ID });

    await screen.findByRole("heading", { name: "Lincoln Red Imps vs Inter Club d'Escaldes" });
    expect(document.body.textContent ?? "").not.toContain("Invalid Date");
    expect(screen.getAllByText("Information indisponible").length).toBeGreaterThan(0);
  });

  it("distinguishes an empty result from an error", async () => {
    await renderPage({ scenario: "empty", matchId: LINCOLN_ANALYST_MATCH_ID });

    expect(await screen.findByText("Aucune analyse disponible")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Réessayer" })).not.toBeInTheDocument();
  });

  it("shows an RFC 9457 error panel for a structured failure", async () => {
    await renderPage({ matchId: "mth_analyst_unavailable" });

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("503 · Model artefact not found")).toBeInTheDocument();
    expect(screen.getByText("/problems/model-artefact-not-found")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Réessayer" })).toBeInTheDocument();
  });

  it("does not retry a 422 problem", async () => {
    await renderPage({ matchId: "mth_analyst_unprocessable" });

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByText("422 · PIT features unavailable")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Réessayer" })).not.toBeInTheDocument();
  });

  it("never prints null, undefined, NaN or Invalid Date on the success path", async () => {
    await renderPage();

    await screen.findByText(/Champions League/);
    const body = document.body.textContent ?? "";
    expect(body).not.toContain("null");
    expect(body).not.toContain("undefined");
    expect(body).not.toContain("NaN");
    expect(body).not.toContain("Invalid Date");
  });

  it("keeps the stacked report readable in a narrow viewport", async () => {
    await renderPage();

    await screen.findByText("Information de valeur");
    expect(screen.getByText("Forces")).toBeInTheDocument();
    expect(screen.getByText("Risques")).toBeInTheDocument();
    expect(screen.getByText("Model Outlook")).toBeInTheDocument();
  });

  it("renders the same published figures in light theme", async () => {
    await renderPage({ theme: "light" });

    expect(await screen.findAllByText("Favori du modèle · Domicile")).not.toHaveLength(0);
    expect(screen.getByText("Valeur détectée · Extérieur")).toBeInTheDocument();
    expect(screen.getAllByText(/-16,7/).length).toBeGreaterThan(0);
  });

  it("still loads football when a leftover sport filter is tennis", async () => {
    renderWithProviders(<AiAnalystView />, { sport: "tennis" });

    expect(
      await screen.findByRole("heading", { name: "Lincoln Red Imps vs Inter Club d'Escaldes" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Analyste limité au football")).not.toBeInTheDocument();
  });

  it("writes the selected match_id into the analyst URL", async () => {
    const user = userEvent.setup();
    await renderPage();

    const select = await screen.findByLabelText("Match");
    const other = [...select.querySelectorAll("option")].find(
      (option) => option.value && option.value !== LINCOLN_ANALYST_MATCH_ID,
    );
    expect(other?.value).toBeTruthy();
    await user.selectOptions(select, other!.value);

    await waitFor(() => {
      expect(navigation.replace).toHaveBeenCalled();
    });
    expect(String(navigation.replace.mock.calls.at(-1)?.[0])).toContain(`match_id=${other!.value}`);
  });
});
