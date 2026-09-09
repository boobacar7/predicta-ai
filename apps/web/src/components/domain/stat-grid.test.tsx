import { StatGrid } from "@/components/domain/stat-grid";
import type { AvailabilityStatus, NamedStat } from "@/types/api";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

function stat(
  key: string,
  label: string,
  value: number | null,
  availability: AvailabilityStatus,
  note: string | null = null,
): NamedStat {
  return {
    key,
    label,
    value,
    unit: value === null ? null : "min",
    quality: {
      availability,
      source: availability === "unavailable" ? null : "test",
      observed_at: availability === "unavailable" ? null : "2026-09-09T18:00:00.000Z",
      freshness: availability === "unavailable" ? null : "fresh",
      note,
    },
  };
}

describe("StatGrid", () => {
  it("renders an available measurement with its unit", () => {
    render(<StatGrid stats={[stat("minutes", "Minutes jouées", 412, "available")]} />);

    expect(screen.getByText("Minutes jouées")).toBeInTheDocument();
    expect(screen.getByText("412 min")).toBeInTheDocument();
  });

  /**
   * The core data-integrity rule: an unavailable statistic is shown as a stated
   * gap. It must never be rendered as 0, which is a real measurement.
   */
  it("renders an unavailable statistic as an explicit gap, never as zero", () => {
    render(
      <StatGrid
        stats={[stat("injuries", "Blessures", null, "unavailable", "Non fournies par la source.")]}
      />,
    );

    expect(screen.getByText("Blessures indisponible")).toBeInTheDocument();
    expect(screen.getByText(/Non fournies par la source/)).toBeInTheDocument();
    expect(screen.queryByText("0")).not.toBeInTheDocument();
  });

  it("treats a null value as a gap even if the source claims availability", () => {
    render(<StatGrid stats={[stat("elo", "Elo", null, "available")]} />);

    expect(screen.getByText("Elo indisponible")).toBeInTheDocument();
  });

  it("still renders a genuine zero as a measurement", () => {
    render(<StatGrid stats={[stat("goals", "Buts", 0, "available")]} />);

    expect(screen.getByText("0 min")).toBeInTheDocument();
    expect(screen.queryByText("Buts indisponible")).not.toBeInTheDocument();
  });

  it("states the absence rather than rendering an empty grid", () => {
    render(<StatGrid stats={[]} />);

    expect(screen.getByText(/Aucun indicateur/)).toBeInTheDocument();
  });
});
