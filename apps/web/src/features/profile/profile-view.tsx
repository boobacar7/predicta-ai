"use client";

import { PageHeader } from "@/components/domain/page-header";
import { Unavailable } from "@/components/domain/unavailable";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { useAuthSession } from "@/features/auth/session-context";
import { pageMeta } from "@/lib/navigation";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

const upcoming = [
  { title: "Favoris", reason: "Les favoris nécessitent encore un suivi produit dédié." },
  { title: "Betting tracker", reason: "Le tracker n'est pas dans le prototype UI." },
  { title: "Abonnement", reason: "Aucun paiement n'est branché à ce stade." },
];

export function ProfileView() {
  const meta = pageMeta["/profile"];
  const { status, user, logout } = useAuthSession();
  const router = useRouter();
  const [pending, setPending] = useState(false);

  async function onLogout() {
    setPending(true);
    try {
      await logout();
      router.replace("/login");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader eyebrow={meta.eyebrow} title={meta.title} description={meta.description} />
      <Card>
        <CardBody className="space-y-4">
          {status === "authenticated" && user ? (
            <>
              <p className="text-sm text-muted">
                Session opaque HttpOnly. PREDICTA AI n’est pas un bookmaker et ne promet aucun
                rendement.
              </p>
              <p className="text-sm">
                Connecté en tant que <span className="font-medium">{user.email}</span>
              </p>
              <Button variant="secondary" onClick={() => void onLogout()} disabled={pending}>
                {pending ? "Déconnexion…" : "Se déconnecter"}
              </Button>
            </>
          ) : (
            <>
              <p className="text-sm text-muted">
                PREDICTA AI n’est pas un bookmaker. La Private Beta utilise une session cookie,
                jamais un jeton dans localStorage.
              </p>
              {status === "disabled" || status === "bypassed" ? (
                <p className="text-sm text-muted">
                  L’API locale n’exige pas de session (mock ou AUTH_BYPASS).
                </p>
              ) : (
                <Button asChild variant="primary">
                  <Link href="/login">Se connecter</Link>
                </Button>
              )}
            </>
          )}
        </CardBody>
      </Card>
      <div className="grid gap-3 md:grid-cols-2">
        {upcoming.map((item) => (
          <Unavailable key={item.title} label={item.title} reason={item.reason} />
        ))}
      </div>
    </div>
  );
}
