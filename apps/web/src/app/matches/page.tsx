import { FOOTBALL_PATHS } from "@/lib/football/routes";
import { redirect } from "next/navigation";

export default function MatchesRedirectPage() {
  redirect(FOOTBALL_PATHS.matches);
}
