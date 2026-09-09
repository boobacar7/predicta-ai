import { PicksView } from "@/features/picks/picks-view";
import { renderWithProviders } from "@/test/render";
import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

/**
 * End-to-end check of one view against the real mock data source.
 *
 * This exercises the whole read path — scenario context, factory, fixtures,
 * QueryBoundary — rather than a stubbed query, so the mandatory states are
 * verified as a user would encounter them.
 */
describe("PicksView", () => {
  it("lists published picks in the nominal scenario", async () => {
    renderWithProviders(<PicksView />, { scenario: "success" });

    expect(await screen.findAllByRole("heading", { level: 3 })).not.toHaveLength(0);
  });

  it("publishes every pick with its model version and triggering criterion", async () => {
    renderWithProviders(<PicksView />, { scenario: "success" });
    const headings = await screen.findAllByRole("heading", { level: 3 });

    // A pick is only meaningful with the version and rule that produced it.
    expect(screen.getAllByText(/^Pick · /)).toHaveLength(headings.length);
    expect(screen.getAllByText(/^Critère : /)).toHaveLength(headings.length);
  });

  it("states that no pick matches, without presenting it as a failure", async () => {
    renderWithProviders(<PicksView />, { scenario: "empty" });

    expect(await screen.findByText("Aucun pick publié")).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    // An empty result is not an error, so it must not offer a retry.
    expect(screen.queryByRole("button", { name: "Réessayer" })).not.toBeInTheDocument();
  });

  it("offers a retry when the simulated provider fails", async () => {
    renderWithProviders(<PicksView />, { scenario: "error" });

    expect(await screen.findByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Réessayer" })).toBeInTheDocument();
  });

  it("never promises an outcome, whatever the scenario", async () => {
    const { container } = renderWithProviders(<PicksView />, { scenario: "success" });
    await screen.findAllByRole("heading", { level: 3 });

    expect(container.textContent ?? "").not.toMatch(/garanti|safe bet|100\s*%\s*s[uû]r/i);
  });
});
