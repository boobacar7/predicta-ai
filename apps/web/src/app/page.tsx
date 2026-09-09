import { DashboardView } from "@/features/dashboard";
import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Dashboard",
};

export default function HomePage() {
  return <DashboardView />;
}
