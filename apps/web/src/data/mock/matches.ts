import { isoHoursFromNow, isoMinutesFromNow, MOCK_NOW_ISO } from "@/data/mock/clock";
import { getLeague, getTeam } from "@/data/mock/catalog";
import { quality, unavailable } from "@/data/mock/quality";
import type {
  MatchDetail,
  MatchSummary,
  OddsSnapshot,
  PredictionDetail,
  ValuePreview,
} from "@/types/api";

const mockSource = "mock.fixtures.v1";

function score(home: number | null, away: number | null, available = true) {
  return {
    home,
    away,
    quality: available
      ? quality({ source: mockSource, observed_at: MOCK_NOW_ISO })
      : unavailable,
  };
}

export const predictions: Record<string, PredictionDetail> = {
  pred_northgate_harbor: {
    id: "pred_northgate_harbor",
    match_id: "mth_northgate_harbor",
    market: "1x2",
    model_family: "ensemble",
    model_version: "fb-ens-2026.08.1",
    calibrator_version: "beta-mc-2026.08.1",
    feature_set_version: "fb-pit-14",
    cutoff_at: isoMinutesFromNow(-90),
    confidence: "high",
    outcomes: [
      outcome("home", "Northgate FC", 0.48, 0.47),
      outcome("draw", "Nul", 0.27, 0.26),
      outcome("away", "Harbor Athletic", 0.25, 0.27),
    ],
    factors: [
      {
        id: "f1",
        label: "Elo domicile",
        direction: "home",
        weight: "high",
        detail: "Écart Elo domicile favorable après calibration saisonnière.",
        quality: quality({ source: mockSource }),
      },
      {
        id: "f2",
        label: "Forme récente",
        direction: "neutral",
        weight: "medium",
        detail: "Cinq derniers matchs disponibles pour les deux clubs.",
        quality: quality({ source: mockSource }),
      },
      {
        id: "f3",
        label: "Compositions",
        direction: "neutral",
        weight: "low",
        detail: "Les compositions officielles ne sont pas dans le jeu de données.",
        quality: unavailable,
      },
    ],
    quality: quality({ source: mockSource, observed_at: isoMinutesFromNow(-90) }),
  },
  pred_riverside_oakmont: {
    id: "pred_riverside_oakmont",
    match_id: "mth_riverside_oakmont",
    market: "1x2",
    model_family: "ensemble",
    model_version: "fb-ens-2026.08.1",
    calibrator_version: "beta-mc-2026.08.1",
    feature_set_version: "fb-pit-14",
    cutoff_at: isoMinutesFromNow(-20),
    confidence: "medium",
    outcomes: [
      outcome("home", "Riverside United", 0.39, 0.38),
      outcome("draw", "Nul", 0.28, 0.29),
      outcome("away", "Oakmont City", 0.33, 0.33),
    ],
    factors: [
      {
        id: "f4",
        label: "Rythme live",
        direction: "away",
        weight: "medium",
        detail: "Les indicateurs live sont partiels : tirs cadrés uniquement.",
        quality: quality({ availability: "partial", note: "xG live indisponible." }),
      },
    ],
    quality: quality({
      availability: "partial",
      source: mockSource,
      note: "Statistiques live incomplètes.",
    }),
  },
  pred_silverpark_westbridge: {
    id: "pred_silverpark_westbridge",
    match_id: "mth_silverpark_westbridge",
    market: "1x2",
    model_family: "ensemble",
    model_version: "fb-ens-2026.08.1",
    calibrator_version: "beta-mc-2026.08.1",
    feature_set_version: "fb-pit-14",
    cutoff_at: isoHoursFromNow(-6),
    confidence: "medium",
    outcomes: [
      outcome("home", "Silverpark", 0.44, 0.43),
      outcome("draw", "Nul", 0.3, 0.31),
      outcome("away", "Westbridge", 0.26, 0.26),
    ],
    factors: [],
    quality: quality({ source: mockSource, freshness: "acceptable" }),
  },
  pred_calder_eastmere: {
    id: "pred_calder_eastmere",
    match_id: "mth_calder_eastmere",
    market: "1x2",
    model_family: "poisson",
    model_version: "fb-pois-2026.07.4",
    calibrator_version: "beta-mc-2026.08.1",
    feature_set_version: "fb-pit-14",
    cutoff_at: isoHoursFromNow(-2),
    confidence: "low",
    outcomes: [
      outcome("home", "Calder Rovers", 0.36, 0.35),
      outcome("draw", "Nul", 0.32, 0.33),
      outcome("away", "Eastmere", 0.32, 0.32),
    ],
    factors: [
      {
        id: "f5",
        label: "Volume d'observations",
        direction: "neutral",
        weight: "high",
        detail: "Échantillon ligue 2 plus réduit : confiance abaissée.",
        quality: quality({ source: mockSource }),
      },
    ],
    quality: quality({ source: mockSource }),
  },
  pred_helix_meridian: {
    id: "pred_helix_meridian",
    match_id: "mth_helix_meridian",
    market: "moneyline",
    model_family: "elo",
    model_version: "bb-elo-2026.06.2",
    calibrator_version: "platt-2026.06.2",
    feature_set_version: "bb-pit-3",
    cutoff_at: isoHoursFromNow(-3),
    confidence: "medium",
    outcomes: [
      outcome("home", "Helix City", 0.58, 0.56),
      outcome("away", "Meridian", 0.42, 0.44),
    ],
    factors: [
      {
        id: "f6",
        label: "Pace domicile",
        direction: "home",
        weight: "medium",
        detail: "Rythme domicile Helix au-dessus de la médiane de ligue.",
        quality: quality({ source: mockSource }),
      },
    ],
    quality: quality({ source: mockSource }),
  },
  pred_voss_elian: {
    id: "pred_voss_elian",
    match_id: "mth_voss_elian",
    market: "winner",
    model_family: "surface_elo",
    model_version: "tn-selo-2026.05.1",
    calibrator_version: "platt-2026.05.1",
    feature_set_version: "tn-pit-2",
    cutoff_at: isoHoursFromNow(-5),
    confidence: "high",
    outcomes: [
      outcome("home", "Lena Voss", 0.62, 0.61),
      outcome("away", "Marco Elian", 0.38, 0.39),
    ],
    factors: [
      {
        id: "f7",
        label: "Elo dur",
        direction: "home",
        weight: "high",
        detail: "Avantage surface dure pour Voss sur le jeu mock.",
        quality: quality({ source: mockSource }),
      },
    ],
    quality: quality({ source: mockSource }),
  },
};

export const odds: Record<string, OddsSnapshot> = {
  odds_northgate_harbor: snapshot(
    "odds_northgate_harbor",
    "mth_northgate_harbor",
    "1x2",
    isoMinutesFromNow(-12),
    "fresh",
    [
      oddsSel("home", "Northgate FC", 2.2),
      oddsSel("draw", "Nul", 3.4),
      oddsSel("away", "Harbor Athletic", 3.5),
    ],
  ),
  odds_riverside_oakmont: snapshot(
    "odds_riverside_oakmont",
    "mth_riverside_oakmont",
    "1x2",
    isoMinutesFromNow(-2),
    "fresh",
    [
      oddsSel("home", "Riverside United", 2.55),
      oddsSel("draw", "Nul", 3.2),
      oddsSel("away", "Oakmont City", 2.85),
    ],
  ),
  odds_silverpark_westbridge: snapshot(
    "odds_silverpark_westbridge",
    "mth_silverpark_westbridge",
    "1x2",
    isoHoursFromNow(-8),
    "stale",
    [
      oddsSel("home", "Silverpark", 2.05),
      oddsSel("draw", "Nul", 3.45),
      oddsSel("away", "Westbridge", 3.8),
    ],
    "Cote observée il y a plus de 8 h. Traiter comme stale.",
  ),
  odds_helix_meridian: snapshot(
    "odds_helix_meridian",
    "mth_helix_meridian",
    "moneyline",
    isoMinutesFromNow(-25),
    "fresh",
    [oddsSel("home", "Helix City", 1.72), oddsSel("away", "Meridian", 2.18)],
  ),
  odds_voss_elian: snapshot(
    "odds_voss_elian",
    "mth_voss_elian",
    "winner",
    isoMinutesFromNow(-40),
    "fresh",
    [oddsSel("home", "Lena Voss", 1.55), oddsSel("away", "Marco Elian", 2.55)],
  ),
};

const valueByMatch: Record<string, ValuePreview> = {
  mth_northgate_harbor: {
    selection: "home",
    edge: 0.015,
    expected_value: 0.034,
    formula_version: "value-engine-0.1",
    quality: quality({ source: mockSource, observed_at: isoMinutesFromNow(-12) }),
  },
  mth_helix_meridian: {
    selection: "away",
    edge: 0.019,
    expected_value: 0.041,
    formula_version: "value-engine-0.1",
    quality: quality({ source: mockSource, observed_at: isoMinutesFromNow(-25) }),
  },
};

export const matches: MatchDetail[] = [
  detail({
    id: "mth_northgate_harbor",
    sport: "football",
    leagueId: "lg_continental",
    homeId: "tm_northgate",
    awayId: "tm_harbor",
    kickoff: isoHoursFromNow(3),
    status: "scheduled",
    venue: "Northgate Park (fictif)",
    score: score(null, null, false),
    predictionId: "pred_northgate_harbor",
    oddsId: "odds_northgate_harbor",
    events: [],
    stats: footballStats(null, null, false),
    form: [
      form("tm_northgate", ["W", "W", "D", "W", "L"]),
      form("tm_harbor", ["D", "W", "L", "W", "D"]),
    ],
    unavailable: [{ field: "lineups", reason: "Compositions non fournies par le jeu mock." }],
  }),
  detail({
    id: "mth_riverside_oakmont",
    sport: "football",
    leagueId: "lg_continental",
    homeId: "tm_riverside",
    awayId: "tm_oakmont",
    kickoff: isoMinutesFromNow(-38),
    status: "live",
    venue: "Riverside Lane (fictif)",
    score: score(1, 1, true),
    predictionId: "pred_riverside_oakmont",
    oddsId: "odds_riverside_oakmont",
    events: [
      event("evt1", 12, "goal", "But Riverside", "tm_riverside"),
      event("evt2", 31, "goal", "But Oakmont", "tm_oakmont"),
    ],
    stats: footballStats(7, 6, true, true),
    form: [
      form("tm_riverside", ["L", "D", "W", "D", "W"]),
      form("tm_oakmont", ["W", "W", "D", "L", "W"]),
    ],
    unavailable: [
      { field: "expected_goals", reason: "xG live indisponible dans ce scénario partiel." },
    ],
  }),
  detail({
    id: "mth_silverpark_westbridge",
    sport: "football",
    leagueId: "lg_continental",
    homeId: "tm_silverpark",
    awayId: "tm_westbridge",
    kickoff: isoHoursFromNow(6),
    status: "scheduled",
    venue: "Silverpark Arena (fictif)",
    score: score(null, null, false),
    predictionId: "pred_silverpark_westbridge",
    oddsId: "odds_silverpark_westbridge",
    events: [],
    stats: footballStats(null, null, false),
    form: [
      form("tm_silverpark", ["D", "D", "W", "L", "D"]),
      form("tm_westbridge", ["L", "W", "L", "D", "W"]),
    ],
    unavailable: [],
  }),
  detail({
    id: "mth_calder_eastmere",
    sport: "football",
    leagueId: "lg_northern",
    homeId: "tm_calder",
    awayId: "tm_eastmere",
    kickoff: isoHoursFromNow(26),
    status: "scheduled",
    venue: "Calder Ground (fictif)",
    score: score(null, null, false),
    predictionId: "pred_calder_eastmere",
    oddsId: null,
    events: [],
    stats: footballStats(null, null, false),
    form: [form("tm_calder", ["W", "L", "W", "W", "D"]), form("tm_eastmere", ["D", "D", "L", "W", "L"])],
    unavailable: [{ field: "odds", reason: "Aucune cote observée pour ce match mock." }],
  }),
  detail({
    id: "mth_helix_meridian",
    sport: "basketball",
    leagueId: "lg_metro",
    homeId: "tm_helix",
    awayId: "tm_meridian",
    kickoff: isoHoursFromNow(5),
    status: "scheduled",
    venue: "Helix Garden (fictif)",
    score: score(null, null, false),
    predictionId: "pred_helix_meridian",
    oddsId: "odds_helix_meridian",
    events: [],
    stats: [],
    form: [form("tm_helix", ["W", "W", "L", "W", "W"]), form("tm_meridian", ["L", "W", "W", "L", "D"])],
    unavailable: [{ field: "player_availability", reason: "Disponibilité joueurs non fournie." }],
  }),
  detail({
    id: "mth_voss_elian",
    sport: "tennis",
    leagueId: "lg_grand_court",
    homeId: "tm_voss",
    awayId: "tm_elian",
    kickoff: isoHoursFromNow(8),
    status: "scheduled",
    venue: "Court Central, Open de Meridia (fictif)",
    score: score(null, null, false),
    predictionId: "pred_voss_elian",
    oddsId: "odds_voss_elian",
    events: [],
    stats: [],
    form: [form("tm_voss", ["W", "W", "W", "L", "W"]), form("tm_elian", ["W", "L", "W", "W", "L"])],
    unavailable: [],
  }),
  detail({
    id: "mth_finished_demo",
    sport: "football",
    leagueId: "lg_continental",
    homeId: "tm_oakmont",
    awayId: "tm_silverpark",
    kickoff: isoHoursFromNow(-20),
    status: "finished",
    venue: "Oakmont Road (fictif)",
    score: score(2, 0, true),
    predictionId: null,
    oddsId: null,
    events: [
      event("evt3", 41, "goal", "But Oakmont", "tm_oakmont"),
      event("evt4", 77, "goal", "But Oakmont", "tm_oakmont"),
    ],
    stats: footballStats(12, 4, true),
    form: [],
    unavailable: [{ field: "prediction", reason: "Prédiction non conservée pour ce match historique mock." }],
  }),
  detail({
    id: "mth_postponed",
    sport: "football",
    leagueId: "lg_northern",
    homeId: "tm_eastmere",
    awayId: "tm_calder",
    kickoff: isoHoursFromNow(4),
    status: "postponed",
    venue: "Eastmere Vale (fictif)",
    score: score(null, null, false),
    predictionId: null,
    oddsId: null,
    events: [],
    stats: footballStats(null, null, false),
    form: [],
    unavailable: [
      { field: "prediction", reason: "Match reporté : aucune prédiction publiée." },
      { field: "odds", reason: "Marché retiré dans le jeu mock." },
    ],
  }),
];

export function toSummary(match: MatchDetail): MatchSummary {
  const prediction = match.prediction;
  const leading = prediction?.outcomes
    .slice()
    .sort(
      (a, b) =>
        (b.calibrated_probability ?? -1) - (a.calibrated_probability ?? -1),
    )[0];

  return {
    id: match.id,
    sport: match.sport,
    league: match.league,
    home: match.home,
    away: match.away,
    kickoff_at: match.kickoff_at,
    status: match.status,
    venue: match.venue,
    score: match.score,
    prediction_preview: prediction
      ? {
          model_version: prediction.model_version,
          market: prediction.market,
          confidence: prediction.confidence,
          leading_selection: leading?.selection ?? "unknown",
          leading_probability: leading?.calibrated_probability ?? null,
          cutoff_at: prediction.cutoff_at,
          outcomes: prediction.outcomes,
          quality: prediction.quality,
        }
      : null,
    value_preview: valueByMatch[match.id] ?? null,
    quality: match.quality,
  };
}

export const matchSummaries: MatchSummary[] = matches.map(toSummary);

function outcome(
  selection: string,
  label: string,
  model: number,
  calibrated: number,
): PredictionDetail["outcomes"][number] {
  return {
    selection,
    label,
    model_probability: model,
    calibrated_probability: calibrated,
    quality: quality({ source: mockSource }),
  };
}

function oddsSel(selection: string, label: string, decimal: number): OddsSnapshot["selections"][number] {
  const implied = 1 / decimal;
  return {
    selection,
    label,
    decimal_odds: decimal,
    implied_probability_raw: implied,
    no_vig_probability: null,
    quality: quality({ source: "mock.bookmaker.atlas" }),
  };
}

function snapshot(
  id: string,
  matchId: string,
  market: string,
  observedAt: string,
  freshness: "fresh" | "stale",
  selections: OddsSnapshot["selections"],
  note?: string,
): OddsSnapshot {
  const overround =
    selections.reduce((sum, item) => sum + (item.implied_probability_raw ?? 0), 0) - 1;
  const totalImplied = selections.reduce(
    (sum, item) => sum + (item.implied_probability_raw ?? 0),
    0,
  );
  const withNoVig = selections.map((item) => ({
    ...item,
    no_vig_probability:
      item.implied_probability_raw === null ? null : item.implied_probability_raw / totalImplied,
  }));

  return {
    id,
    match_id: matchId,
    market,
    bookmaker: "Atlas (fictif)",
    provider: "mock.odds.atlas",
    observed_at: observedAt,
    overround,
    selections: withNoVig,
    quality: quality({
      source: "mock.odds.atlas",
      observed_at: observedAt,
      freshness,
      availability: freshness === "stale" ? "stale" : "available",
      note: note ?? null,
    }),
  };
}

function form(teamId: string, results: Array<"W" | "D" | "L">) {
  return {
    team_id: teamId,
    results,
    quality: quality({ source: mockSource }),
  };
}

function event(id: string, minute: number, type: string, label: string, teamId: string) {
  return {
    id,
    minute,
    type,
    label,
    team_id: teamId,
    quality: quality({ source: mockSource }),
  };
}

function footballStats(
  homeShots: number | null,
  awayShots: number | null,
  available: boolean,
  partial = false,
) {
  const q = available
    ? quality({
        source: mockSource,
        availability: partial ? "partial" : "available",
        note: partial ? "xG et possession live indisponibles." : null,
      })
    : unavailable;

  return [
    {
      key: "shots",
      label: "Tirs",
      home_value: homeShots,
      away_value: awayShots,
      unit: "count",
      quality: q,
    },
    {
      key: "xg",
      label: "xG",
      home_value: null,
      away_value: null,
      unit: "expected_goals",
      quality: unavailable,
    },
  ];
}

function detail(input: {
  id: string;
  sport: MatchDetail["sport"];
  leagueId: string;
  homeId: string;
  awayId: string;
  kickoff: string;
  status: MatchDetail["status"];
  venue: string;
  score: MatchDetail["score"];
  predictionId: string | null;
  oddsId: string | null;
  events: MatchDetail["timeline"];
  stats: MatchDetail["stats"];
  form: MatchDetail["form"];
  unavailable: MatchDetail["unavailable_fields"];
}): MatchDetail {
  const home = getTeam(input.homeId);
  const away = getTeam(input.awayId);
  const prediction = input.predictionId ? predictions[input.predictionId] ?? null : null;
  const oddsSnap = input.oddsId ? odds[input.oddsId] ?? null : null;

  return {
    id: input.id,
    sport: input.sport,
    league: getLeague(input.leagueId),
    home,
    away,
    kickoff_at: input.kickoff,
    status: input.status,
    venue: input.venue,
    score: input.score,
    prediction_preview: null,
    value_preview: valueByMatch[input.id] ?? null,
    quality: quality({
      source: mockSource,
      availability: input.status === "postponed" ? "unavailable" : "available",
      freshness: oddsSnap?.quality.freshness === "stale" ? "stale" : "fresh",
      note: "Fixture fictive. Ne pas interpréter comme un événement réel.",
    }),
    timeline: input.events,
    stats: input.stats,
    odds: oddsSnap,
    prediction,
    form: input.form,
    unavailable_fields: input.unavailable,
  };
}

