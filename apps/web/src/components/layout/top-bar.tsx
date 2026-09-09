"use client";

import { SportFilter } from "@/components/domain/filters";
import { Button } from "@/components/ui/button";
import {
  DropdownContent,
  DropdownItem,
  DropdownRoot,
  DropdownTrigger,
} from "@/components/ui/dropdown";
import { useFilters } from "@/lib/filters/context";
import type { MockScenario } from "@/types/api";
import { Menu } from "lucide-react";

const scenarios: Array<{ value: MockScenario; label: string }> = [
  { value: "success", label: "Succès" },
  { value: "empty", label: "Vide" },
  { value: "partial", label: "Partiel" },
  { value: "stale", label: "Stale" },
  { value: "error", label: "Erreur" },
];

export function TopBar({ onOpenNav }: { onOpenNav: () => void }) {
  const { sport, setSport, scenario, setScenario } = useFilters();

  return (
    <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3 md:px-8">
      <div className="flex items-center gap-2">
        <Button
          size="icon"
          variant="ghost"
          className="lg:hidden"
          onClick={onOpenNav}
          aria-label="Ouvrir la navigation"
        >
          <Menu className="size-5" />
        </Button>
        <SportFilter value={sport} onChange={setSport} />
      </div>
      <DropdownRoot>
        <DropdownTrigger asChild>
          <Button size="sm" variant="ghost">
            Scénario mock : {scenarios.find((item) => item.value === scenario)?.label}
          </Button>
        </DropdownTrigger>
        <DropdownContent>
          {scenarios.map((item) => (
            <DropdownItem
              key={item.value}
              active={item.value === scenario}
              onSelect={() => setScenario(item.value)}
            >
              {item.label}
            </DropdownItem>
          ))}
        </DropdownContent>
      </DropdownRoot>
    </div>
  );
}
