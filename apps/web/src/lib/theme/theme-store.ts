import {
  applyTheme,
  DEFAULT_THEME,
  persistTheme,
  readStoredTheme,
  type Theme,
} from "@/lib/theme/theme";

let current: Theme = DEFAULT_THEME;
const listeners = new Set<() => void>();

if (typeof window !== "undefined") {
  current = readStoredTheme(window.localStorage);
  applyTheme(current);
}

function emit() {
  for (const listener of listeners) {
    listener();
  }
}

export function subscribeTheme(listener: () => void): () => void {
  listeners.add(listener);
  return () => {
    listeners.delete(listener);
  };
}

export function getThemeSnapshot(): Theme {
  return current;
}

export function getServerThemeSnapshot(): Theme {
  return DEFAULT_THEME;
}

export function setThemeStore(theme: Theme, persist = true): void {
  current = theme;
  if (typeof document !== "undefined") {
    applyTheme(theme);
  }
  if (persist && typeof window !== "undefined") {
    persistTheme(theme, window.localStorage);
  }
  emit();
}

export function toggleThemeStore(persist = true): Theme {
  const next = current === "dark" ? "light" : "dark";
  setThemeStore(next, persist);
  return next;
}

/** Re-reads `localStorage` into the in-memory store. Used after a remount. */
export function hydrateThemeFromStorage(): void {
  if (typeof window === "undefined") {
    return;
  }

  current = readStoredTheme(window.localStorage);
  applyTheme(current);
}

/** Test seam: drops in-memory theme so a new provider starts from the default. */
export function resetThemeStore(): void {
  current = DEFAULT_THEME;
}
