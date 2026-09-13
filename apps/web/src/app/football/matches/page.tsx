import { MatchCenterView } from "@/features/matches";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Match Center" };

export default function FootballMatchesPage() {
  return <MatchCenterView />;
}
