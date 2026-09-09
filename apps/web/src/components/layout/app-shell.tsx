"use client";

import { MockBanner } from "@/components/domain/mock-banner";
import { BottomNav } from "@/components/layout/bottom-nav";
import { MobileNav } from "@/components/layout/mobile-nav";
import { PageFade } from "@/components/layout/page-fade";
import { Sidebar } from "@/components/layout/sidebar";
import { TopBar } from "@/components/layout/top-bar";
import { MockScenarioProvider } from "@/data/mock/scenario-context";
import { FiltersProvider } from "@/lib/filters/context";
import { usePathname } from "next/navigation";
import { useState, type ReactNode } from "react";

/**
 * Application chrome.
 *
 * Navigation adapts across three breakpoints: a persistent 256px sidebar from
 * `lg`, an overlay drawer on tablet, and a bottom bar of primary destinations
 * on mobile.
 */
export function AppShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [navOpen, setNavOpen] = useState(false);

  return (
    <FiltersProvider>
      <MockScenarioProvider>
        <a
          href="#contenu"
          className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-ai focus:px-3 focus:py-2"
        >
          Aller au contenu
        </a>
        <div className="min-h-screen bg-background">
          <MockBanner />
          <div className="flex">
            <aside className="sticky top-0 hidden h-screen w-64 shrink-0 border-r border-border bg-background lg:block">
              <Sidebar />
            </aside>
            <div className="min-w-0 flex-1">
              <TopBar onOpenNav={() => setNavOpen(true)} />
              <main id="contenu" className="px-4 py-6 pb-24 md:px-8 md:pb-10">
                <PageFade key={pathname}>{children}</PageFade>
              </main>
            </div>
          </div>
          <MobileNav open={navOpen} onOpenChange={setNavOpen} />
          <BottomNav />
        </div>
      </MockScenarioProvider>
    </FiltersProvider>
  );
}
