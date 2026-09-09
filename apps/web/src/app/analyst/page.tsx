import { AnalystView } from "@/features/analyst";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "AI Analyst" };

export default function AnalystPage() {
  return <AnalystView />;
}
