import { isoMinutesFromNow, MOCK_NOW_ISO } from "@/data/mock/clock";
import { matches } from "@/data/mock/matches";
import type { AnalystSession, Fact, FactPack } from "@/types/api";

function factsFor(matchId: string): Fact[] {
  const match = matches.find((item) => item.id === matchId);
  if (!match) return [];

  const facts: Fact[] = [
    {
      id: `${matchId}_kickoff`,
      label: "Coup d'envoi",
      value: match.kickoff_at,
      unit: "timestamp",
      source: "mock.fixtures.v1",
      observed_at: MOCK_NOW_ISO,
      availability: "available",
    },
    {
      id: `${matchId}_status`,
      label: "Statut",
      value: match.status,
      unit: null,
      source: "mock.fixtures.v1",
      observed_at: MOCK_NOW_ISO,
      availability: "available",
    },
  ];

  if (match.prediction) {
    for (const outcome of match.prediction.outcomes) {
      facts.push({
        id: `${matchId}_p_${outcome.selection}`,
        label: `Probabilité calibrée · ${outcome.label}`,
        value:
          outcome.calibrated_probability === null
            ? "unavailable"
            : String(outcome.calibrated_probability),
        unit: "probability",
        source: match.prediction.model_version,
        observed_at: match.prediction.cutoff_at,
        availability: outcome.calibrated_probability === null ? "unavailable" : "available",
      });
    }
    facts.push({
      id: `${matchId}_model`,
      label: "Version de modèle",
      value: match.prediction.model_version,
      unit: null,
      source: "mock.registry",
      observed_at: match.prediction.cutoff_at,
      availability: "available",
    });
  }

  for (const field of match.unavailable_fields) {
    facts.push({
      id: `${matchId}_missing_${field.field}`,
      label: field.field,
      value: "unavailable",
      unit: null,
      source: "mock.fixtures.v1",
      observed_at: MOCK_NOW_ISO,
      availability: "unavailable",
    });
  }

  return facts;
}

export function createFactPack(matchId: string): FactPack {
  return {
    id: `fp_${matchId}`,
    match_id: matchId,
    generated_at: MOCK_NOW_ISO,
    facts: factsFor(matchId),
  };
}

export function createAnalystSession(matchId: string, question?: string): AnalystSession {
  const match = matches.find((item) => item.id === matchId);
  const factPack = createFactPack(matchId);
  const availableFacts = factPack.facts.filter((fact) => fact.availability === "available");
  const missing = factPack.facts.filter((fact) => fact.availability === "unavailable");
  const cited = availableFacts.slice(0, 4).map((fact) => fact.id);
  const leading = match?.prediction?.outcomes
    .slice()
    .sort(
      (a, b) => (b.calibrated_probability ?? -1) - (a.calibrated_probability ?? -1),
    )[0];
  const leadingProbability =
    leading?.calibrated_probability === null || leading?.calibrated_probability === undefined
      ? "indisponible"
      : `${(leading.calibrated_probability * 100).toFixed(0)} %`;

  const body = match?.prediction
    ? [
        `À partir du fact pack ${factPack.id}, le modèle ${match.prediction.model_version} attribue la plus haute probabilité calibrée à ${leading?.label ?? "une issue"} (${leadingProbability}).`,
        "Cette valeur est une estimation statistique, pas un résultat futur.",
        missing.length
          ? `Champs explicitement indisponibles : ${missing.map((item) => item.label).join(", ")}. Ils n'ont pas été complétés.`
          : "Aucun champ manquant n'est signalé dans ce paquet.",
      ].join(" ")
    : "Aucune prédiction n'est présente dans le fact pack. L'analyste ne peut pas inventer de probabilités.";

  const messages = [
    ...(question
      ? [
          {
            id: `msg_user_${matchId}`,
            role: "user" as const,
            body: question,
            cited_fact_ids: [],
            created_at: isoMinutesFromNow(-1),
          },
        ]
      : []),
    {
      id: `msg_analyst_${matchId}`,
      role: "analyst" as const,
      body,
      cited_fact_ids: cited,
      created_at: MOCK_NOW_ISO,
    },
  ];

  return {
    match_id: matchId,
    fact_pack: factPack,
    messages,
    llm_model: "mock-explainer-0.1",
    prompt_version: "analyst-prompt-0.1",
    disclaimer:
      "Réponse mock construite uniquement à partir du fact pack. Aucune donnée absente n'a été extrapolée.",
  };
}

export const defaultAnalystMatchId = "mth_northgate_harbor";
