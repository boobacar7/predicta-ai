import { AnalyticsView } from "@/features/analytics";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Statistiques" };

export default function AnalyticsPage() {
  return <AnalyticsView />;
}
