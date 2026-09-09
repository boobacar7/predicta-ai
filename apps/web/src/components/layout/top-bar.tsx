"use client";

import { SportFilter } from "@/components/domain/filters";
import { Button } from "@/components/ui/button";
import {
  DropdownContent,
  DropdownItem,
  DropdownRoot,
  DropdownTrigger,
} from "@/components/ui/dropdown";
import { MOCK_SCENARIOS, useMockScenarioControl } from "@/data/mock/scenario-context";
import { getDataSourceKind } from "@/lib/config";
import { useFilters } from "@/lib/filters/context";
import { Menu } from "lucide-react";

export function TopBar({ onOpenNav }: { onOpenNav: () => void }) {
  const { sport, setSport } = useFilters();
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
        <SportFilter value={sport} onChange={setSport} />
      </div>
      {showScenarioPicker ? <ScenarioPicker /> : null}
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
