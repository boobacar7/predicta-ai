"use client";

import * as Dropdown from "@radix-ui/react-dropdown-menu";
import { cn } from "@/lib/cn";
import type { ReactNode } from "react";

export const DropdownRoot = Dropdown.Root;
export const DropdownTrigger = Dropdown.Trigger;

export function DropdownContent({ children }: { children: ReactNode }) {
  return (
    <Dropdown.Portal>
      <Dropdown.Content
        sideOffset={8}
        className="z-50 min-w-44 rounded-xl border border-border bg-surface-elevated p-1 shadow-xl"
      >
        {children}
      </Dropdown.Content>
    </Dropdown.Portal>
  );
}

export function DropdownItem({
  children,
  onSelect,
  active = false,
}: {
  children: ReactNode;
  onSelect?: () => void;
  active?: boolean;
}) {
  return (
    <Dropdown.Item
      onSelect={onSelect}
      className={cn(
        "cursor-pointer rounded-lg px-3 py-2 text-sm text-muted outline-none hover:bg-surface-hover hover:text-foreground",
        active && "bg-ai-soft text-foreground",
      )}
    >
      {children}
    </Dropdown.Item>
  );
}
