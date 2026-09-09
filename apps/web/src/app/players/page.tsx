import { PlayersView } from "@/features/players";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Joueurs" };

export default function PlayersPage() {
  return <PlayersView />;
}
