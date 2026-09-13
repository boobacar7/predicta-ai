import { DashboardView } from "@/features/dashboard";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Football",
};

export default function FootballDashboardPage() {
  return <DashboardView />;
}
