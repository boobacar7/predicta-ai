import { DataSourceError } from "@/lib/api/errors";
import {
  isFootballPredictionUnavailable,
  shouldFetchFootballPrediction,
} from "@/lib/football/prediction-query";
import { describe, expect, it } from "vitest";

describe("shouldFetchFootballPrediction", () => {
  it("fetches for scheduled and live matches", () => {
    expect(shouldFetchFootballPrediction({ status: "scheduled" })).toBe(true);
    expect(shouldFetchFootballPrediction({ status: "live" })).toBe(true);
  });

  it("does not fetch a pre-match prediction for finished or postponed matches", () => {
    expect(shouldFetchFootballPrediction({ status: "finished" })).toBe(false);
    expect(shouldFetchFootballPrediction({ status: "postponed" })).toBe(false);
  });

  it("does not fetch the engine for a catalogue prototype model", () => {
    expect(
      shouldFetchFootballPrediction({
        status: "scheduled",
        catalogueModelVersion: "fb-ens-2026.08.1",
      }),
    ).toBe(false);
  });
});

describe("isFootballPredictionUnavailable", () => {
  it("treats 404 and 422 as an unpublished prediction", () => {
    expect(isFootballPredictionUnavailable(new DataSourceError({ kind: "not_found", status: 404 }))).toBe(
      true,
    );
    expect(
      isFootballPredictionUnavailable(new DataSourceError({ kind: "server", status: 422 })),
    ).toBe(true);
  });

  it("does not swallow retryable transport failures", () => {
    expect(isFootballPredictionUnavailable(new DataSourceError({ kind: "network" }))).toBe(false);
    expect(isFootballPredictionUnavailable(new DataSourceError({ kind: "server", status: 503 }))).toBe(
      false,
    );
  });
});
