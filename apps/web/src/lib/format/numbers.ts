const APP_LOCALE = "fr-FR";

const percentFormatter = new Intl.NumberFormat(APP_LOCALE, {
  minimumFractionDigits: 0,
  maximumFractionDigits: 1,
});

const decimalFormatter = new Intl.NumberFormat(APP_LOCALE, {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
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

export function formatProbability(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "Indisponible";
  }

  return `${percentFormatter.format(value * 100)} %`;
}

export function formatPoints(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "Indisponible";
  }

  return `${signedPointsFormatter.format(value * 100)} pts`;
}

export function formatDecimalOdds(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "Indisponible";
  }

  return decimalFormatter.format(value);
}

export function formatSignedPercent(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "Indisponible";
  }

  return `${signedPercentFormatter.format(value * 100)} %`;
}

export function formatCount(value: number): string {
  return new Intl.NumberFormat(APP_LOCALE).format(value);
}

export function formatScore(value: number | null | undefined): string {
  if (value === null || value === undefined) {
    return "—";
  }

  return String(value);
}
