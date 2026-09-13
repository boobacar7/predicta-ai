import { AiPicksView } from "@/features/picks";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "AI Picks" };

export default function FootballAiPicksPage() {
  return <AiPicksView />;
}
