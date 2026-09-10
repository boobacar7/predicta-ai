"use client";

import { NavIcon } from "@/components/layout/nav-icon";
import { cn } from "@/lib/cn";
import Link from "next/link";
import { usePathname } from "next/navigation";

const items = [
  { href: "/", label: "Home", icon: "layout" as const },
  { href: "/matches", label: "Matchs", icon: "calendar" as const },
  { href: "/ai-picks", label: "Picks", icon: "spark" as const },
  { href: "/value-finder", label: "Value", icon: "diamond" as const },
  { href: "/analyst", label: "Analyst", icon: "message" as const },
];

export function BottomNav() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="Raccourcis mobiles"
      className="fixed inset-x-0 bottom-0 z-40 border-t border-border bg-background/95 backdrop-blur md:hidden"
    >
      <ul className="grid grid-cols-5">
        {items.map((item) => {
          const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "flex flex-col items-center gap-1 py-2 text-[10px]",
                  active ? "text-ai-strong" : "text-muted",
                )}
              >
                <NavIcon name={item.icon} className="size-4" />
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
