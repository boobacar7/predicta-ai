/**
 * Display formatting for numeric values.
 *
 * Numbers travel through the app raw and are formatted only at the render
 * boundary. Every helper maps a missing value to an explicit "Indisponible"
 * label: an absent measurement must never be shown as `0`, which the product
 * spec treats as a distinct and meaningful figure.
 */

const APP_LOCALE = "fr-FR";

/** Rendered whenever a value is absent or unusable. */
export const UNAVAILABLE_LABEL = "Indisponible";

/** Rendered for a slot that has no value by nature, such as an unplayed score. */
export const NO_VALUE_LABEL = "—";

/**
 * Narrow no-break space (U+202F).
 *
 * French typography separates a number from its unit, and a plain space would
 * let a `%` sign or a unit wrap onto its own line inside a narrow card.
 */
const NNBSP = "\u202f";

const percentFormatter = new Intl.NumberFormat(APP_LOCALE, {
  minimumFractionDigits: 0,
  maximumFractionDigits: 1,
});

const decimalFormatter = new Intl.NumberFormat(APP_LOCALE, {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});

const metricFormatter = new Intl.NumberFormat(APP_LOCALE, {
  minimumFractionDigits: 3,
  maximumFractionDigits: 3,
});

const signedPointsFormatter = new Intl.NumberFormat(APP_LOCALE, {
  signDisplay: "always",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

const signedPercentFormatter = new Intl.NumberFormat(APP_LOCALE, {
  signDisplay: "always",
  minimumFractionDigits: 1,
  maximumFractionDigits: 1,
});

const countFormatter = new Intl.NumberFormat(APP_LOCALE);

function isMissing(value: number | null | undefined): value is null | undefined {
  return value === null || value === undefined || Number.isNaN(value);
}

/** A probability in `[0, 1]` rendered as a percentage. */
export function formatProbability(value: number | null | undefined): string {
  if (isMissing(value)) return UNAVAILABLE_LABEL;
  return `${percentFormatter.format(value * 100)}${NNBSP}%`;
}

/** A probability difference rendered in percentage points, always signed. */
export function formatPoints(value: number | null | undefined): string {
  if (isMissing(value)) return UNAVAILABLE_LABEL;
  return `${signedPointsFormatter.format(value * 100)}${NNBSP}pts`;
}

export function formatDecimalOdds(value: number | null | undefined): string {
  if (isMissing(value)) return UNAVAILABLE_LABEL;
  return decimalFormatter.format(value);
}

/** A signed ratio such as expected value or ROI, rendered as a percentage. */
export function formatSignedPercent(value: number | null | undefined): string {
  if (isMissing(value)) return UNAVAILABLE_LABEL;
  return `${signedPercentFormatter.format(value * 100)}${NNBSP}%`;
}

/**
 * A raw model metric kept on its own scale: log loss, Brier score, ECE.
 * These are not percentages and must not be rescaled for display.
 */
export function formatMetric(value: number | null | undefined): string {
  if (isMissing(value)) return UNAVAILABLE_LABEL;
  return metricFormatter.format(value);
}

/** An integer quantity, such as a number of predictions. */
export function formatCount(value: number | null | undefined): string {
  if (isMissing(value)) return UNAVAILABLE_LABEL;
  return countFormatter.format(value);
}

/** A rating or other plain numeric indicator, shown without forced decimals. */
export function formatNumber(value: number | null | undefined): string {
  if (isMissing(value)) return UNAVAILABLE_LABEL;
  return countFormatter.format(value);
}

/** A score slot. An unplayed match has no score; that is not missing data. */
export function formatScore(value: number | null | undefined): string {
  if (isMissing(value)) return NO_VALUE_LABEL;
  return String(value);
}
