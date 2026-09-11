"use client";

import { Button } from "@/components/ui/button";
import { useTheme } from "@/lib/theme/theme-provider";
import { Moon, Sun } from "lucide-react";

export function ThemeToggle() {
  const { theme, toggleTheme } = useTheme();
  const next = theme === "dark" ? "clair" : "sombre";

  return (
    <Button
      type="button"
      size="icon"
      variant="ghost"
      onClick={toggleTheme}
      aria-label={`Activer le thème ${next}`}
      aria-pressed={theme === "light"}
      title={theme === "dark" ? "Thème sombre" : "Thème clair"}
    >
      {theme === "dark" ? <Moon className="size-4" aria-hidden="true" /> : <Sun className="size-4" aria-hidden="true" />}
      <span className="sr-only">Thème actuel : {theme === "dark" ? "sombre" : "clair"}</span>
    </Button>
  );
}
