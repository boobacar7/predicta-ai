import { MatchDetailView } from "@/features/matches";

export default async function FootballMatchPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return <MatchDetailView matchId={id} />;
}
