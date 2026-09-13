import { FOOTBALL_PATHS } from "@/lib/football/routes";
import { redirect } from "next/navigation";

export default function AnalystRedirectPage() {
  redirect(FOOTBALL_PATHS.aiAnalyst);
}
