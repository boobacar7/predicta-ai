import { TeamDetailView } from "@/features/teams";

export default async function TeamPage({ params }: PageProps<"/teams/[id]">) {
  const { id } = await params;
  return <TeamDetailView teamId={id} />;
}
