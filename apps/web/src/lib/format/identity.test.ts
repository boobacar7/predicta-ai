import { UNKNOWN_IDENTITY_LABEL, formatKickoffOrUnknown, formatMatchup } from "@/lib/format/identity";
import { describe, expect, it } from "vitest";

describe("formatMatchup", () => {
  it("renders both canonical labels when the archive resolved them", () => {
    const matchup = formatMatchup("Lincoln Red Imps", "Inter Club d'Escaldes");

    expect(matchup).toEqual({
      resolved: true,
      home: "Lincoln Red Imps",
      away: "Inter Club d'Escaldes",
      text: "Lincoln Red Imps vs Inter Club d'Escaldes",
    });
  });

  it("keeps the resolved side when the other label is missing", () => {
    const homeOnly = formatMatchup("Lincoln Red Imps", null);
    const awayOnly = formatMatchup(null, "Inter Club d'Escaldes");

    expect(homeOnly.resolved).toBe(false);
    expect(homeOnly.text).toBe(`Lincoln Red Imps vs ${UNKNOWN_IDENTITY_LABEL}`);
    expect(awayOnly.text).toBe(`${UNKNOWN_IDENTITY_LABEL} vs Inter Club d'Escaldes`);
  });

  it("never prints null, undefined or NaN", () => {
    const matchup = formatMatchup(null, undefined);

    expect(matchup.text).toBe(`${UNKNOWN_IDENTITY_LABEL} vs ${UNKNOWN_IDENTITY_LABEL}`);
    expect(JSON.stringify(matchup)).not.toContain("null");
    expect(matchup.home).not.toBe("undefined");
    expect(matchup.away).not.toBe("NaN");
  });
});

describe("formatKickoffOrUnknown", () => {
  it("formats a valid RFC 3339 kickoff", () => {
    const formatted = formatKickoffOrUnknown("2026-07-07T16:00:00Z");

    expect(formatted).not.toBe(UNKNOWN_IDENTITY_LABEL);
    expect(formatted).toMatch(/7/);
    expect(formatted).not.toContain("Invalid Date");
  });

  it("labels an absent or unparseable kickoff instead of rendering Invalid Date", () => {
    expect(formatKickoffOrUnknown(null)).toBe(UNKNOWN_IDENTITY_LABEL);
    expect(formatKickoffOrUnknown("")).toBe(UNKNOWN_IDENTITY_LABEL);
    expect(formatKickoffOrUnknown("not-a-date")).toBe(UNKNOWN_IDENTITY_LABEL);
  });
});
