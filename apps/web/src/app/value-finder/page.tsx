import { ValueFinderView } from "@/features/value";
import type { Metadata } from "next";
import { Suspense } from "react";

export const metadata: Metadata = { title: "Value Finder" };

export default function ValueFinderPage() {
  return (
    <Suspense>
      <ValueFinderView />
    </Suspense>
  );
}
