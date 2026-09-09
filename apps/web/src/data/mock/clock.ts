/**
 * Injected clock for deterministic mock timestamps.
 * Prototype "now" is fixed to keep fixtures stable across reloads.
 */
export const MOCK_NOW_ISO = "2026-09-09T18:00:00.000Z";

export function mockNow(): Date {
  return new Date(MOCK_NOW_ISO);
}

export function isoMinutesFromNow(minutes: number): string {
  return new Date(mockNow().getTime() + minutes * 60_000).toISOString();
}

export function isoHoursFromNow(hours: number): string {
  return isoMinutesFromNow(hours * 60);
}

export function isoDaysFromNow(days: number): string {
  return isoHoursFromNow(days * 24);
}
