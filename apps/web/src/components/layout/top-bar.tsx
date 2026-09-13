"use client";

import { EnvelopeDataModeBadge } from "@/components/domain/envelope-data-mode";
import { ThemeToggle } from "@/components/layout/theme-toggle";
import { Button } from "@/components/ui/button";
import {
  DropdownContent,
  DropdownItem,
  DropdownRoot,
  DropdownTrigger,
} from "@/components/ui/dropdown";
import { MOCK_SCENARIOS, useMockScenarioControl } from "@/data/mock/scenario-context";
import { getDataSourceKind } from "@/lib/config";
import { Menu } from "lucide-react";

export function TopBar({ onOpenNav }: { onOpenNav: () => void }) {
  const showScenarioPicker = getDataSourceKind() !== "http";

  return (
    <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3 md:px-8">
      <div className="flex min-w-0 items-center gap-2">
        <Button
          size="icon"
          variant="ghost"
          className="lg:hidden"
          onClick={onOpenNav}
          aria-label="Ouvrir la navigation"
        >
          <Menu className="size-5" />
        </Button>
        <span
          className="h-8 rounded-full bg-ai-soft px-3 text-xs font-medium leading-8 text-foreground"
          aria-label="Sport verrouillé : football"
        >
          Football
        </span>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <EnvelopeDataModeBadge />
        <ThemeToggle />
        {showScenarioPicker ? <ScenarioPicker /> : null}
      </div>
    </div>
  );
}

/** Inspection control for the fixture states. Hidden once the API serves everything. */
function ScenarioPicker() {
  const { scenario, setScenario } = useMockScenarioControl();
  const active = MOCK_SCENARIOS.find((item) => item.value === scenario);

  return (
    <DropdownRoot>
      <DropdownTrigger asChild>
        <Button size="sm" variant="ghost" className="shrink-0">
          <span className="hidden sm:inline">Scénario mock&nbsp;: </span>
          {active?.label}
        </Button>
      </DropdownTrigger>
      <DropdownContent>
        {MOCK_SCENARIOS.map((item) => (
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
  );
}
