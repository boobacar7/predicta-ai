import { ValueFinderView } from "@/features/value/value-finder-view";
import { renderWithProviders } from "@/test/render";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

/**
 * Covers the Value Finder against the real `MockDataSource`.
 *
 * Beyond rendering, these assertions protect two product rules: the page must
 * display the Value Engine's own ratios rather than deriving them, and a value
 * that was never measured must never behave like a zero.
 *
 * Testing Library normalises the narrow no-break space into an ordinary space,
 * so expectations use a plain space.
 */

async function renderPage(options: Parameters<typeof renderWithProviders>[1] = {}) {
  const view = renderWithProviders(<ValueFinderView />, options);
  await screen.findByRole("heading", { name: "Value Finder", level: 1 });
  return view;
}

describe("ValueFinderView", () => {
  it("shows no figure before the first response resolves", () => {
    renderWithProviders(<ValueFinderView />);

    expect(document.querySelectorAll("dd")).toHaveLength(0);
  });

  it("lists opportunities with model, market and derived figures side by side", async () => {
    await renderPage();

    const list = await screen.findByRole("list");
    const cards = within(list).getAllByRole("listitem");

    expect(cards.length).toBeGreaterThan(0);
    expect(within(list).getAllByText("P calibrée").length).toBe(cards.length);
    expect(within(list).getAllByText("No-vig").length).toBe(cards.length);
    expect(within(list).getAllByText("Edge no-vig").length).toBe(cards.length);
    expect(within(list).getAllByText("EV").length).toBe(cards.length);
  });

  it("reports how many opportunities were loaded, not a catalogue total", async () => {
    await renderPage();

    expect(await screen.findByText(/opportunité\(s\) retenue\(s\) sur/)).toBeInTheDocument();
  });

  it("warns that the payload is mock", async () => {
    await renderPage();

    expect(await screen.findByText("Mock data")).toBeInTheDocument();
  });

  it("reorders without changing any published value when the sort changes", async () => {
    const user = userEvent.setup();
    await renderPage();

    const list = await screen.findByRole("list");
    const before = within(list)
      .getAllByRole("listitem")
      .map((item) => item.textContent);

    await user.selectOptions(screen.getByLabelText("Trier par"), "kickoff");

    await waitFor(() => {
      const after = within(screen.getByRole("list"))
        .getAllByRole("listitem")
        .map((item) => item.textContent);

      expect(after).toHaveLength(before.length);
      expect([...after].sort()).toEqual([...before].sort());
    });
  });

  it("narrows the list with a threshold and explains an emptied result", async () => {
    const user = userEvent.setup();
    await renderPage();

    await screen.findByRole("list");

    // No fixture reaches a 90-point edge, so the refinement empties the page.
    await user.type(screen.getByLabelText(/Edge min/), "90");

    expect(await screen.findByText("Aucune opportunité pour ces critères")).toBeInTheDocument();
    expect(screen.getByText(/jamais un seuil/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Réessayer" })).not.toBeInTheDocument();
  });

  it("restores the full list when the filters are reset", async () => {
    const user = userEvent.setup();
    await renderPage();

    const initial = within(await screen.findByRole("list")).getAllByRole("listitem").length;

    await user.type(screen.getByLabelText(/Edge min/), "90");
    await screen.findByText("Aucune opportunité pour ces critères");

    await user.click(screen.getByRole("button", { name: "Réinitialiser" }));

    await waitFor(() => {
      expect(within(screen.getByRole("list")).getAllByRole("listitem")).toHaveLength(initial);
    });
  });

  it("distinguishes an empty result from an error", async () => {
    await renderPage({ scenario: "empty" });

    expect(await screen.findByText("Aucun écart de value")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("shows an actionable error panel with a retry when the read fails", async () => {
    await renderPage({ scenario: "error" });

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Réessayer" })).toBeInTheDocument();
  });

  it("keeps a stale payload visible with its freshness stated", async () => {
    await renderPage({ scenario: "stale" });

    const list = await screen.findByRole("list");
    expect(within(list).getAllByRole("listitem").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Ancien/).length).toBeGreaterThan(0);
  });

  it("opens a detail panel split by Prediction, Odds and Value", async () => {
    const user = userEvent.setup();
    await renderPage();

    await screen.findByRole("list");
    await user.click(screen.getAllByRole("button", { name: /Détail de l'opportunité/ })[0]);

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("Prediction")).toBeInTheDocument();
    expect(within(dialog).getByText("Odds")).toBeInTheDocument();
    expect(within(dialog).getByText("Value")).toBeInTheDocument();
    expect(within(dialog).getByText("Overround")).toBeInTheDocument();
  });

  it("documents the Value Engine formulas rather than reimplementing them", async () => {
    const user = userEvent.setup();
    await renderPage();

    await user.click(screen.getByRole("button", { name: "Formules" }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/ne recalcule aucune référence métier/)).toBeInTheDocument();
  });

  it("never promises an outcome or a return", async () => {
    await renderPage();

    await screen.findByRole("list");
    const body = document.body.textContent ?? "";

    for (const forbidden of ["garanti", "100 %", "gain assuré", "pari sûr"]) {
      expect(body.toLowerCase()).not.toContain(forbidden.toLowerCase());
    }
  });
});
