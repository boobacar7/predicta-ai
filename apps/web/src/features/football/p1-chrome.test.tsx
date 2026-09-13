import { BottomNav } from "@/components/layout/bottom-nav";
import { Sidebar } from "@/components/layout/sidebar";
import { TopBar } from "@/components/layout/top-bar";
import { DashboardView } from "@/features/dashboard/dashboard-view";
import { renderWithProviders } from "@/test/render";
import { screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

vi.mock("next/navigation", () => ({
  usePathname: () => "/football",
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

describe("P1 football chrome", () => {
  it("advertises only football routes and locks the sport", async () => {
    renderWithProviders(
      <>
        <TopBar onOpenNav={() => undefined} />
        <Sidebar />
        <BottomNav />
      </>,
    );

    expect(screen.getByLabelText("Sport verrouillé : football")).toHaveTextContent("Football");
    expect(screen.queryByText("Tous les sports")).not.toBeInTheDocument();
    expect(screen.queryByText("Basketball")).not.toBeInTheDocument();
    expect(screen.queryByText("Tennis")).not.toBeInTheDocument();

    expect(screen.getByRole("link", { name: "Dashboard" })).toHaveAttribute("href", "/football");
    expect(screen.getByRole("link", { name: "Match Center" })).toHaveAttribute(
      "href",
      "/football/matches",
    );
    expect(screen.getByRole("link", { name: "AI Picks" })).toHaveAttribute(
      "href",
      "/football/ai-picks",
    );
    expect(screen.getByRole("link", { name: "Value Finder" })).toHaveAttribute(
      "href",
      "/football/value",
    );
    expect(screen.getByRole("link", { name: "AI Analyst" })).toHaveAttribute(
      "href",
      "/football/ai-analyst",
    );

    expect(screen.queryByRole("link", { name: "Statistiques" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Ligues" })).not.toBeInTheDocument();
  });

  it("shows envelope data_mode in chrome, not only the config kind", async () => {
    renderWithProviders(
      <>
        <TopBar onOpenNav={() => undefined} />
        <DashboardView />
      </>,
    );

    expect(await screen.findByLabelText("data_mode mock")).toBeInTheDocument();
    expect(screen.getByText(/data_mode · mock/)).toBeInTheDocument();
  });
});
