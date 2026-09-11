"use client";

import { CandidateModelNotice } from "@/components/domain/model-status";
import { PageHeader } from "@/components/domain/page-header";
import { PrototypeNotice } from "@/components/domain/prototype-notice";
import { Unavailable } from "@/components/domain/unavailable";
import { FOOTBALL_MODEL_VERSION } from "@/data/mock/football-engine";
import { pageMeta } from "@/lib/navigation";

const meta = pageMeta["/performance"];

/**
 * Performance of the football candidate model is not published by a stable API.
 *
 * GET /performance still exists as a prototype catalogue route. This page no
 * longer presents fb-ens-* metrics as if they were football-elo-v1-candidate.
 */
export function PerformanceView() {
  return (
    <div className="space-y-6">
      <PageHeader eyebrow={meta.eyebrow} title={meta.title} description={meta.description} />

      <CandidateModelNotice version={FOOTBALL_MODEL_VERSION} status="candidate" />

      <Unavailable
        label="Log loss, Brier, accuracy, ECE et ROI théorique"
        reason="Aucune API football stable ne publie encore ces métriques pour le modèle candidat."
      />

      <PrototypeNotice>
        L&apos;ancienne série fb-ens-* appartient au prototype catalogue. Elle n&apos;est plus
        affichée ici pour éviter de la confondre avec le moteur football.
      </PrototypeNotice>
    </div>
  );
}
