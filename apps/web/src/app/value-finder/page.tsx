import { FOOTBALL_PATHS } from "@/lib/football/routes";
import { redirect } from "next/navigation";

export default function ValueFinderRedirectPage() {
  redirect(FOOTBALL_PATHS.value);
}
