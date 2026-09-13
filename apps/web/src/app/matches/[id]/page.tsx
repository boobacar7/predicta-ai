import { footballMatchPath } from "@/lib/football/routes";
import { redirect } from "next/navigation";

export default async function MatchRedirectPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  redirect(footballMatchPath(id));
}
