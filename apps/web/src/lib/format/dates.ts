const utcDate: Intl.DateTimeFormatOptions = {
  timeZone: "UTC",
  hourCycle: "h23",
};

export function parseTimestamp(value: string): Date {
  return new Date(value);
}

export function formatKickoff(value: string): string {
  return new Intl.DateTimeFormat("fr-FR", {
    ...utcDate,
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parseTimestamp(value));
}

export function formatShortDate(value: string): string {
  return new Intl.DateTimeFormat("fr-FR", {
    ...utcDate,
    weekday: "short",
    day: "numeric",
    month: "short",
  }).format(parseTimestamp(value));
}

export function formatClock(value: string): string {
  return new Intl.DateTimeFormat("fr-FR", {
    ...utcDate,
    hour: "2-digit",
    minute: "2-digit",
  }).format(parseTimestamp(value));
}

export function formatAbsolute(value: string): string {
  return `${new Intl.DateTimeFormat("fr-FR", {
    ...utcDate,
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(parseTimestamp(value))} UTC`;
}

export function formatWeekday(value: string): string {
  return new Intl.DateTimeFormat("fr-FR", {
    ...utcDate,
    weekday: "short",
  }).format(parseTimestamp(value));
}

export function formatDayNumber(value: string): string {
  return new Intl.DateTimeFormat("fr-FR", {
    ...utcDate,
    day: "numeric",
  }).format(parseTimestamp(value));
}

export function formatRelativeTo(value: string, now: Date): string {
  const diffMs = parseTimestamp(value).getTime() - now.getTime();
  const minutes = Math.round(diffMs / 60_000);
  const abs = Math.abs(minutes);
  const formatter = new Intl.RelativeTimeFormat("fr-FR", { numeric: "auto" });

  if (abs < 60) {
    return formatter.format(minutes, "minute");
  }

  const hours = Math.round(minutes / 60);
  if (Math.abs(hours) < 48) {
    return formatter.format(hours, "hour");
  }

  return formatter.format(Math.round(hours / 24), "day");
}
