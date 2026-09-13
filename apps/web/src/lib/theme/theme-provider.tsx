"use client";

import {
  getServerThemeSnapshot,
  getThemeSnapshot,
  setThemeStore,
  subscribeTheme,
  toggleThemeStore,
} from "@/lib/theme/theme-store";
import type { Theme } from "@/lib/theme/theme";
import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useSyncExternalStore,
  type ReactNode,
} from "react";

interface ThemeContextValue {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  toggleTheme: () => void;
}

const ThemeContext = createContext<ThemeContextValue | null>(null);

export function ThemeProvider({
  children,
  persist = true,
}: {
  children: ReactNode;
  initialTheme?: Theme;
  persist?: boolean;
}) {
  const theme = useSyncExternalStore(
    subscribeTheme,
    getThemeSnapshot,
    getServerThemeSnapshot,
  );

  const setTheme = useCallback(
    (next: Theme) => {
      setThemeStore(next, persist);
    },
    [persist],
  );

  const toggleTheme = useCallback(() => {
    toggleThemeStore(persist);
  }, [persist]);

  const value = useMemo(
    () => ({ theme, setTheme, toggleTheme }),
    [theme, setTheme, toggleTheme],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
}

export function useTheme(): ThemeContextValue {
  const context = useContext(ThemeContext);

  if (!context) {
    throw new Error("useTheme must be used within ThemeProvider");
  }

  return context;
}
