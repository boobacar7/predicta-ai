import { FOOTBALL_PATHS } from "@/lib/football/routes";
import { redirect } from "next/navigation";

export default function AiPicksRedirectPage() {
  redirect(FOOTBALL_PATHS.aiPicks);
}
