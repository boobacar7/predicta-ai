import { AiPicksView } from "@/features/picks/ai-picks-view";
import { renderWithProviders } from "@/test/render";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

/**
 * End-to-end coverage of the page against the real `MockDataSource`, so the
 * whole chain is exercised: hook, query key, data source, selectors, states.
 *
 * These assertions are product rules, not snapshots. They fail if the page
 * starts promising an outcome, invents a team name, hides why it is empty, or
 * drops the candidate-model and mock-data warnings.
 */

async function renderPage(scenario: Parameters<typeof renderWithProviders>[1] = {}) {
  const view = renderWithProviders(<AiPicksView />, scenario);
  await screen.findByRole("heading", { name: "AI Picks", level: 1 });
  return view;
}

/**
 * Testing Library normalises the narrow no-break space used by French
 * typography into an ordinary space before matching, so expectations are
 * written with a plain space.
 */

describe("AiPicksView", () => {
  it("shows no figure at all before the first response resolves", () => {
    renderWithProviders(<AiPicksView />);

    expect(screen.queryByText("Rang 1")).not.toBeInTheDocument();
    expect(document.querySelectorAll("dd")).toHaveLength(0);
  });

  it("lists ranked opportunities with the figures the engine published", async () => {
    await renderPage();

    expect(await screen.findByText("Rang 1")).toBeInTheDocument();
    expect(screen.getAllByText(/^Rang \d+$/)).toHaveLength(4);

    // Best pick: P 31,3 %, odds 5.00, edge +11,3 pts, EV +56,3 %.
    expect(screen.getAllByText("31,3 %").length).toBeGreaterThan(0);
    expect(screen.getAllByText("5,00").length).toBeGreaterThan(0);
    expect(screen.getAllByText("+11,3 pts").length).toBeGreaterThan(0);
    expect(screen.getAllByText("+56,3 %").length).toBeGreaterThan(0);
  });

  it("warns that the payload is mock and names the fictional odds provider", async () => {
    await renderPage();

    expect(await screen.findByText("Mock data")).toBeInTheDocument();
    expect(screen.getByText(/fournisseur fictif/)).toBeInTheDocument();
    expect(screen.getAllByText("predicta-mock-odds-v0.1").length).toBeGreaterThan(0);
  });

  it("warns that the model is a candidate and repeats it on every card", async () => {
    await renderPage();

    expect(await screen.findByText("Modèle candidat")).toBeInTheDocument();
    expect(screen.getByText(/ni champion ni promu en production/)).toBeInTheDocument();
    expect(screen.getAllByText("football-elo-v1-candidate").length).toBeGreaterThan(1);
  });

  /** The engine publishes no team identity; guessing one would be fabricated data. */
  it("identifies a match by its id rather than inventing team names", async () => {
    await renderPage();

    const list = await screen.findByRole("list", { name: "Opportunités classées" });

    // Two selections of the same match, each labelled by the same identifier.
    expect(within(list).getAllByText("mth_mock_northgate_harbor")).toHaveLength(2);
    expect(within(list).getAllByText("Continental Premier").length).toBeGreaterThan(0);
  });

  it("summarises the total from the engine and scopes averages to the page", async () => {
    await renderPage();

    const total = await screen.findByText("Opportunités");
    expect(within(total.closest("div") as HTMLElement).getByText("4")).toBeInTheDocument();
    expect(screen.getAllByText(/sur 4 affiché/).length).toBeGreaterThan(0);
  });

  it("explains rejected selections instead of dropping them silently", async () => {
    await renderPage();

    expect(await screen.findByText(/sélections écartées/)).toBeInTheDocument();
    expect(screen.getByText("EV négative")).toBeInTheDocument();
    expect(screen.getByText("Marché 1X2 incomplet")).toBeInTheDocument();
  });

  it("re-queries the engine when a threshold filter changes", async () => {
    const user = userEvent.setup();
    await renderPage();

    await screen.findByText("Rang 1");
    expect(screen.getAllByText(/^Rang \d+$/)).toHaveLength(4);

    // 5 points of edge keeps the two opportunities above it (+11,3 and +7,6).
    await user.type(screen.getByLabelText(/Edge min/), "5");

    await waitFor(() => {
      expect(screen.getAllByText(/^Rang \d+$/)).toHaveLength(2);
    });

    // The rejected ones are reported with the rule that rejected them.
    expect(await screen.findByText("Edge sous le seuil demandé")).toBeInTheDocument();
  });

  it("filters by competition without leaving the page blank", async () => {
    const user = userEvent.setup();
    await renderPage();

    await screen.findByText("Rang 1");
    await user.selectOptions(screen.getByLabelText("Compétition"), "Northern Championship");

    await waitFor(() => {
      const list = screen.getByRole("list", { name: "Opportunités classées" });
      expect(within(list).queryAllByText("mth_mock_northgate_harbor")).toHaveLength(0);
      expect(within(list).getByText("mth_mock_castleford_riverton")).toBeInTheDocument();
    });
  });

  it("locks the sport selector, because the engine only covers football", async () => {
    await renderPage();

    expect(screen.getByLabelText("Sport")).toBeDisabled();
  });

  it("states that the engine has no coverage for another sport, without faking one", async () => {
    renderWithProviders(<AiPicksView />, { sport: "tennis" });

    expect(await screen.findByText("Moteur limité au football")).toBeInTheDocument();
    expect(screen.queryByText(/^Rang /)).not.toBeInTheDocument();
  });

  it("distinguishes an empty result from an error, and offers no retry", async () => {
    await renderPage({ scenario: "empty" });

    expect(await screen.findByText("Aucune opportunité éligible")).toBeInTheDocument();
    expect(screen.getByText(/C'est un résultat, pas une erreur/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Réessayer" })).not.toBeInTheDocument();
  });

  it("shows an actionable error panel with a retry when the read fails", async () => {
    await renderPage({ scenario: "error" });

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Réessayer" })).toBeInTheDocument();
  });

  it("opens a detail panel split by Prediction, Odds and Value", async () => {
    const user = userEvent.setup();
    await renderPage();

    await screen.findByText("Rang 1");
    await user.click(screen.getAllByRole("button", { name: /Détail de l'opportunité/ })[0]);

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Prediction")).toBeInTheDocument();
    expect(within(dialog).getByText("Odds")).toBeInTheDocument();
    expect(within(dialog).getByText("Value")).toBeInTheDocument();
    expect(
      within(dialog).getByText(/ne publie ni nom d'équipe ni horaire/),
    ).toBeInTheDocument();
  });

  it("never promises an outcome or a return", async () => {
    await renderPage();

    await screen.findByText("Rang 1");
    const body = document.body.textContent ?? "";

    for (const forbidden of ["garanti", "sûr à", "100 %", "gain assuré", "pari sûr"]) {
      expect(body.toLowerCase()).not.toContain(forbidden.toLowerCase());
    }
  });
});
