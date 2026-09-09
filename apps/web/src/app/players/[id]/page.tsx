import { PlayerDetailView } from "@/features/players";

export default async function PlayerPage({ params }: PageProps<"/players/[id]">) {
  const { id } = await params;
  return <PlayerDetailView playerId={id} />;
}
