import { LeagueDetailView } from "@/features/leagues";

export default async function LeaguePage({ params }: PageProps<"/leagues/[id]">) {
  const { id } = await params;
  return <LeagueDetailView leagueId={id} />;
}
