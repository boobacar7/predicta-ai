"use client";

import { useTheme } from "@/lib/theme/theme-provider";
import { useMemo } from "react";

export interface ChartColors {
  grid: string;
  axis: string;
  tooltipBackground: string;
  tooltipBorder: string;
  tooltipText: string;
  ai: string;
  secondary: string;
}

const FALLBACK: ChartColors = {
  grid: "rgba(245, 247, 250, 0.06)",
  axis: "#8992A3",
  tooltipBackground: "#151b25",
  tooltipBorder: "rgba(245, 247, 250, 0.1)",
  tooltipText: "#f5f7fa",
  ai: "#7c6cf6",
  secondary: "#4ea3d9",
};

function readCssColor(name: string, fallback: string): string {
  if (typeof document === "undefined") {
    return fallback;
  }

  const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return value || fallback;
}

export function readChartColors(): ChartColors {
  return {
    grid: readCssColor("--border", FALLBACK.grid),
    axis: readCssColor("--muted", FALLBACK.axis),
    tooltipBackground: readCssColor("--surface-elevated", FALLBACK.tooltipBackground),
    tooltipBorder: readCssColor("--border-strong", FALLBACK.tooltipBorder),
    tooltipText: readCssColor("--foreground", FALLBACK.tooltipText),
    ai: readCssColor("--ai", FALLBACK.ai),
    secondary: readCssColor("--away", FALLBACK.secondary),
  };
}

/**
 * Chart strokes and surfaces follow the active theme tokens.
 * The series data themselves are never rewritten.
 */
export function useChartColors(): ChartColors {
  const { theme } = useTheme();

  return useMemo(() => {
    void theme;
    return typeof document === "undefined" ? FALLBACK : readChartColors();
  }, [theme]);
}
