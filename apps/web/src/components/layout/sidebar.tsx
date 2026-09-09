"use client";

import { NavIcon } from "@/components/layout/nav-icon";
import { navSections, profileNavItem } from "@/lib/navigation";
import { cn } from "@/lib/cn";
import Link from "next/link";
import { usePathname } from "next/navigation";

export function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <div className="flex h-full flex-col">
      <Link href="/" className="flex items-center gap-3 px-4 py-5" onClick={onNavigate}>
        <span className="flex size-9 items-center justify-center rounded-xl bg-ai-soft text-sm font-semibold text-ai-strong">
          P
        </span>
        <span>
          <span className="block text-sm font-medium tracking-tight">PREDICTA</span>
          <span className="block text-[11px] uppercase tracking-[0.18em] text-faint">AI</span>
        </span>
      </Link>
      <nav aria-label="Principal" className="flex-1 space-y-6 overflow-y-auto px-3 pb-6">
        {navSections.map((section) => (
          <div key={section.id}>
            <p className="px-3 pb-2 text-[11px] uppercase tracking-[0.18em] text-faint">
              {section.label}
            </p>
            <ul className="space-y-1">
              {section.items.map((item) => (
                <li key={item.href}>
                  <NavLink item={item} pathname={pathname} onNavigate={onNavigate} />
                </li>
              ))}
            </ul>
          </div>
        ))}
      </nav>
      <div className="border-t border-border p-3">
        <NavLink item={profileNavItem} pathname={pathname} onNavigate={onNavigate} />
      </div>
    </div>
  );
}

function NavLink({
  item,
  pathname,
  onNavigate,
}: {
  item: (typeof profileNavItem);
  pathname: string;
  onNavigate?: () => void;
}) {
  const active = item.href === "/" ? pathname === "/" : pathname.startsWith(item.href);

  return (
    <Link
      href={item.href}
      onClick={onNavigate}
      aria-current={active ? "page" : undefined}
      className={cn(
        "flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition-colors",
        active
          ? "bg-ai-soft text-foreground"
          : "text-muted hover:bg-surface-hover hover:text-foreground",
      )}
    >
      <NavIcon name={item.icon} className="size-4" />
      {item.label}
    </Link>
  );
}
