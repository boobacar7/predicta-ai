"use client";

import { PageHeader } from "@/components/domain/page-header";
import { Unavailable } from "@/components/domain/unavailable";
import { Card, CardBody } from "@/components/ui/card";
import { pageMeta } from "@/lib/navigation";

const upcoming = [
  { title: "Compte", reason: "L'authentification arrive en phase 10." },
  { title: "Favoris", reason: "Les favoris nécessitent un utilisateur authentifié." },
  { title: "Betting tracker", reason: "Le tracker n'est pas dans le prototype UI." },
  { title: "Abonnement", reason: "Aucun paiement n'est branché à ce stade." },
];

export function ProfileView() {
  const meta = pageMeta["/profile"];

  return (
    <div className="space-y-6">
      <PageHeader eyebrow={meta.eyebrow} title={meta.title} description={meta.description} />
      <Card>
        <CardBody>
          <p className="text-sm text-muted">
            PREDICTA AI n’est pas un bookmaker. Ce profil exposera plus tard des préférences
            d’affichage, jamais un compte de mise.
          </p>
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
