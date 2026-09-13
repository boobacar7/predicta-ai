import { FOOTBALL_PATHS } from "@/lib/football/routes";
import { redirect } from "next/navigation";

export default function HomeRedirectPage() {
  redirect(FOOTBALL_PATHS.dashboard);
}
