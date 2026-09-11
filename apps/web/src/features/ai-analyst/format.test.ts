import { formatFactorValue, selectionSideLabel } from "@/features/ai-analyst/format";
import { UNKNOWN_IDENTITY_LABEL } from "@/lib/format/identity";
import { formatPoints, formatProbability, formatSignedPercent } from "@/lib/format/numbers";
import { describe, expect, it } from "vitest";

describe("formatFactorValue", () => {
  it("formats published ratios without inventing a replacement", () => {
    expect(
      formatFactorValue({
        type: "model_probability",
        label: "P",
        value: 0.4165,
        direction: "home",
        source: "test",
      }),
    ).toBe(formatProbability(0.4165));
    expect(
      formatFactorValue({
        type: "edge",
        label: "Edge",
        value: -0.0835,
        direction: "home",
        source: "test",
      }),
    ).toBe(formatPoints(-0.0835));
    expect(
      formatFactorValue({
        type: "ev",
        label: "EV",
        value: -0.167,
        direction: "home",
        source: "test",
      }),
    ).toBe(formatSignedPercent(-0.167));
  });

  it("never prints null, undefined or NaN", () => {
    expect(
      formatFactorValue({
        type: "model_status",
        label: "Statut",
        value: null,
        direction: "neutral",
        source: "test",
      }),
    ).toBe(UNKNOWN_IDENTITY_LABEL);
    expect(
      formatFactorValue({
        type: "ev",
        label: "EV",
        value: Number.NaN,
        direction: "home",
        source: "test",
      }),
    ).toBe(UNKNOWN_IDENTITY_LABEL);
  });
});

describe("selectionSideLabel", () => {
  it("labels a missing selection as unavailable", () => {
    expect(selectionSideLabel(null)).toBe(UNKNOWN_IDENTITY_LABEL);
    expect(selectionSideLabel("AWAY")).toBe("Extérieur");
  });
});
