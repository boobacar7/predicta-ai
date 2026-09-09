import type { AvailabilityStatus, DataQuality, FreshnessLevel } from "@/types/api";
import { MOCK_NOW_ISO } from "@/data/mock/clock";

export function quality(options: {
  availability?: AvailabilityStatus;
  source?: string | null;
  observed_at?: string | null;
  freshness?: FreshnessLevel | null;
  note?: string | null;
} = {}): DataQuality {
  const availability = options.availability ?? "available";

  return {
    availability,
    source: options.source ?? (availability === "unavailable" ? null : "mock.fixtures"),
    observed_at:
      options.observed_at ?? (availability === "unavailable" ? null : MOCK_NOW_ISO),
    freshness:
      options.freshness ??
      (availability === "stale" ? "stale" : availability === "unavailable" ? null : "fresh"),
    note: options.note ?? null,
  };
}

export const unavailable = quality({
  availability: "unavailable",
  source: null,
  observed_at: null,
  freshness: null,
  note: "Donnée absente du jeu mock. Ce n'est pas une valeur nulle.",
});
