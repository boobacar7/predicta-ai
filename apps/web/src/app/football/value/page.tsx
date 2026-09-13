import { ValueFinderView } from "@/features/value";
import type { Metadata } from "next";
import { Suspense } from "react";

export const metadata: Metadata = { title: "Value Finder" };

export default function FootballValuePage() {
  return (
    <Suspense>
      <ValueFinderView />
    </Suspense>
  );
}
