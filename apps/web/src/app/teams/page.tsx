import { TeamsView } from "@/features/teams";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Équipes" };

export default function TeamsPage() {
  return <TeamsView />;
}
