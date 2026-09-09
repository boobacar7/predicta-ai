import { ProfileView } from "@/features/profile";
import type { Metadata } from "next";

export const metadata: Metadata = { title: "Profil" };

export default function ProfilePage() {
  return <ProfileView />;
}
