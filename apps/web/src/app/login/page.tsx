import { LoginView } from "@/features/auth";
import type { Metadata } from "next";
import { Suspense } from "react";

export const metadata: Metadata = { title: "Connexion" };

export default function LoginPage() {
  return (
    <Suspense fallback={<p className="text-sm text-muted">Chargement…</p>}>
      <LoginView />
    </Suspense>
  );
}
