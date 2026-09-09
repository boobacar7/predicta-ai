import { LeaguesView } from "@/features/leagues";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Ligues" };

export default function LeaguesPage() {
  return <LeaguesView />;
}
