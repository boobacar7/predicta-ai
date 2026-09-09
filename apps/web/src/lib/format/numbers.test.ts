import {
  NO_VALUE_LABEL,
  UNAVAILABLE_LABEL,
  formatCount,
  formatDecimalOdds,
  formatMetric,
  formatNumber,
  formatPoints,
  formatProbability,
  formatScore,
  formatSignedPercent,
} from "@/lib/format/numbers";
import { describe, expect, it } from "vitest";

/** Non-breaking space, produced by the fr-FR locale before a percent sign. */
const NBSP = "\u202f";

describe("probability and percentage formatting", () => {
  it("renders a probability as a French percentage", () => {
    expect(formatProbability(0.681)).toBe(`68,1${NBSP}%`);
    expect(formatProbability(0)).toBe(`0${NBSP}%`);
    expect(formatProbability(1)).toBe(`100${NBSP}%`);
  });

  it("always signs an expected value or ROI", () => {
    expect(formatSignedPercent(0.072)).toBe(`+7,2${NBSP}%`);
    expect(formatSignedPercent(-0.084)).toBe(`-8,4${NBSP}%`);
  });

  it("renders an edge in percentage points, signed", () => {
    expect(formatPoints(0.072)).toBe(`+7,2${NBSP}pts`);
    expect(formatPoints(-0.031)).toBe(`-3,1${NBSP}pts`);
  });

  it("keeps the unit attached to the number so it cannot wrap alone", () => {
    expect(formatProbability(0.5)).not.toContain(" ");
    expect(formatPoints(0.05)).not.toContain(" ");
  });
});

describe("model metrics keep their own scale", () => {
  it("does not rescale log loss, Brier or ECE into percentages", () => {
    expect(formatMetric(0.981)).toBe("0,981");
    expect(formatMetric(0.238)).toBe("0,238");
    expect(formatMetric(0.031)).toBe("0,031");
  });
});

describe("odds and counts", () => {
  it("renders decimal odds with two decimals", () => {
    expect(formatDecimalOdds(2.5)).toBe("2,50");
  });

  it("renders counts as integers", () => {
    expect(formatCount(640)).toBe("640");
  });
});

/**
 * The product spec forbids presenting an absent measurement as a number.
 * Zero is a real, meaningful value and must stay distinguishable from a gap.
 */
describe("missing values never become zero", () => {
  const formatters = {
    formatProbability,
    formatPoints,
    formatDecimalOdds,
    formatSignedPercent,
    formatMetric,
    formatCount,
    formatNumber,
  };

  for (const [name, format] of Object.entries(formatters)) {
    it(`${name} labels null and undefined as unavailable`, () => {
      expect(format(null)).toBe(UNAVAILABLE_LABEL);
      expect(format(undefined)).toBe(UNAVAILABLE_LABEL);
      expect(format(Number.NaN)).toBe(UNAVAILABLE_LABEL);
    });

    it(`${name} still renders an explicit zero`, () => {
      expect(format(0)).not.toBe(UNAVAILABLE_LABEL);
    });
  }

  it("distinguishes an unplayed score from an unavailable measurement", () => {
    expect(formatScore(null)).toBe(NO_VALUE_LABEL);
    expect(formatScore(0)).toBe("0");
  });
});
