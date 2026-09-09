import { PerformanceView } from "@/features/performance";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Performance" };

export default function PerformancePage() {
  return <PerformanceView />;
}
