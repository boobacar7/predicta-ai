import { ValueFinderView } from "@/features/value/value-finder-view";
import { renderWithProviders } from "@/test/render";
import { screen } from "@testing-library/react";
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
  usePathname: () => "/value-finder",
}));

async function renderPage(options: Parameters<typeof renderWithProviders>[1] = {}) {
  navigation.matchId = "";
  const view = renderWithProviders(<ValueFinderView />, options);
  await screen.findByRole("heading", { name: "Value Finder", level: 1 });
  return view;
}

describe("ValueFinderView", () => {
  beforeEach(() => {
    navigation.matchId = "";
    navigation.replace.mockReset();
  });

  it("shows no figure before the first response resolves", () => {
    renderWithProviders(<ValueFinderView />);

    expect(document.querySelectorAll("dd")).toHaveLength(0);
  });

  it("reads GET /football/value rather than the legacy GET /value catalogue", async () => {
    await renderPage();

    expect(await screen.findByText("Information de valeur")).toBeInTheDocument();
    expect(screen.getAllByText("Lincoln Red Imps vs Inter Club d'Escaldes").length).toBeGreaterThan(0);
    expect(screen.getByText(/Affinage local/)).toBeInTheDocument();
    expect(screen.queryByText("Northgate FC · Harbor Athletic")).not.toBeInTheDocument();
  });

  it("copies HOME, DRAW and AWAY figures from the Value Engine", async () => {
    await renderPage();

    expect(await screen.findByText("Information de valeur")).toBeInTheDocument();
    expect(screen.getByText("Domicile")).toBeInTheDocument();
    expect(screen.getByText("Nul")).toBeInTheDocument();
    expect(screen.getByText("Extérieur")).toBeInTheDocument();
    expect(screen.getByText("-16,7 %")).toBeInTheDocument();
    expect(screen.getByText("+56,3 %")).toBeInTheDocument();
  });

  it("warns that the payload is mock and the model is a candidate", async () => {
    await renderPage();

    expect(await screen.findByText("Mock data")).toBeInTheDocument();
    expect(screen.getAllByText("Modèle candidat").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/football-elo-v1-candidate/).length).toBeGreaterThan(0);
    expect(screen.queryByText(/^Production$/)).not.toBeInTheDocument();
  });

  it("reorders without changing published values when the sort changes", async () => {
    const user = userEvent.setup();
    await renderPage();

    const before = (await screen.findByRole("list")).textContent;
    await user.selectOptions(screen.getByLabelText("Trier par"), "ev");
    const after = screen.getByRole("list").textContent;

    expect(after).toContain("-16,7");
    expect(after).toContain("+56,3");
    expect(before).toContain("-16,7");
  });

  it("never uses bookmaker recommendation language", async () => {
    await renderPage();
    await screen.findByText("Information de valeur");

    expect(document.body.textContent).not.toMatch(/pari recommandé|mise conseillée|safe bet/i);
  });
});
