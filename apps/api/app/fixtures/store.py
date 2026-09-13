from collections.abc import Sequence
from dataclasses import dataclass

from app.core.clock import Clock
from app.fixtures.quality import quality, unavailable
from app.schemas import (
    AvailabilityStatus,
    CalibrationBucket,
    FormResult,
    FreshnessLevel,
    Insight,
    League,
    MatchDetail,
    MatchEvent,
    MatchStatistic,
    MatchStatus,
    MatchSummary,
    ModelHealthSummary,
    OddsSelection,
    OddsSnapshot,
    PerformanceReport,
    PerformanceSeriesPoint,
    Pick,
    Player,
    PredictionDetail,
    PredictionFactor,
    ProbabilityOutcome,
    Scoreline,
    Sport,
    SportCode,
    Team,
    TeamFormSide,
    UnavailableField,
)
from app.value_engine import calculator


@dataclass
class FixtureStore:
    sports: list[Sport]
    leagues: list[League]
    teams: list[Team]
    players: list[Player]
    matches: list[MatchDetail]
    picks: list[Pick]
    insights: list[Insight]
    performance: PerformanceReport


def build_store(clock: Clock) -> FixtureStore:
    sports = [
        Sport(id="sport_football", name="Football", code="football"),
        Sport(id="sport_basketball", name="Basketball", code="basketball"),
        Sport(id="sport_tennis", name="Tennis", code="tennis"),
    ]
    leagues = [
        League(
            id="lg_continental",
            name="Continental Premier",
            sport="football",
            country="Europe (fictif)",
            season="2026-27",
            tier=1,
        ),
        League(
            id="lg_northern",
            name="Northern Championship",
            sport="football",
            country="Nord (fictif)",
            season="2026-27",
            tier=2,
        ),
        League(
            id="lg_metro",
            name="Metro Basketball League",
            sport="basketball",
            country="Atlantique (fictif)",
            season="2026",
            tier=1,
        ),
        League(
            id="lg_grand_court",
            name="Grand Court Tour",
            sport="tennis",
            country="International (fictif)",
            season="2026",
            tier=1,
        ),
    ]
    teams = [
        _team("tm_northgate", "Northgate FC", "Northgate", "NGF", "football", "lg_continental"),
        _team("tm_harbor", "Harbor Athletic", "Harbor", "HAR", "football", "lg_continental"),
        _team("tm_riverside", "Riverside United", "Riverside", "RSU", "football", "lg_continental"),
        _team("tm_oakmont", "Oakmont City", "Oakmont", "OAK", "football", "lg_continental"),
        _team("tm_silverpark", "Silverpark", "Silverpark", "SLV", "football", "lg_continental"),
        _team("tm_westbridge", "Westbridge", "Westbridge", "WBR", "football", "lg_continental"),
        _team("tm_calder", "Calder Rovers", "Calder", "CAL", "football", "lg_northern"),
        _team("tm_eastmere", "Eastmere", "Eastmere", "EST", "football", "lg_northern"),
        _team("tm_helix", "Helix City", "Helix", "HLX", "basketball", "lg_metro"),
        _team("tm_meridian", "Meridian", "Meridian", "MRD", "basketball", "lg_metro"),
        _team("tm_voss", "Lena Voss", "Voss", "VOS", "tennis", "lg_grand_court"),
        _team("tm_elian", "Marco Elian", "Elian", "ELI", "tennis", "lg_grand_court"),
    ]
    players = [
        Player(
            id="pl_voss",
            name="Lena Voss",
            sport="tennis",
            team_id=None,
            position="Droitier, fond de court",
            country="SVE (fictif)",
        ),
        Player(
            id="pl_elian",
            name="Marco Elian",
            sport="tennis",
            team_id=None,
            position="Gaucher, service-volée",
            country="ITA (fictif)",
        ),
        Player(
            id="pl_kade",
            name="Jonas Kade",
            sport="football",
            team_id="tm_northgate",
            position="Milieu",
            country="NED (fictif)",
        ),
        Player(
            id="pl_orla",
            name="Orla Simms",
            sport="football",
            team_id="tm_harbor",
            position="Attaquant",
            country="IRL (fictif)",
        ),
        Player(
            id="pl_nara",
            name="Nara Ellison",
            sport="basketball",
            team_id="tm_helix",
            position="Meneur",
            country="USA (fictif)",
        ),
    ]

    q = quality(clock)
    predictions = {
        "pred_northgate_harbor": PredictionDetail(
            id="pred_northgate_harbor",
            match_id="mth_northgate_harbor",
            market="1x2",
            model_family="ensemble",
            model_version="fb-ens-2026.08.1",
            calibrator_version="beta-mc-2026.08.1",
            feature_set_version="fb-pit-14",
            cutoff_at=clock.shift(minutes=-90),
            confidence="high",
            outcomes=[
                _outcome(clock, "home", "Northgate FC", 0.48, 0.47),
                _outcome(clock, "draw", "Nul", 0.27, 0.26),
                _outcome(clock, "away", "Harbor Athletic", 0.25, 0.27),
            ],
            factors=[
                PredictionFactor(
                    id="f1",
                    label="Elo domicile",
                    direction="home",
                    weight="high",
                    detail="Écart Elo domicile favorable après calibration saisonnière (mock).",
                    quality=q,
                ),
                PredictionFactor(
                    id="f2",
                    label="Forme récente",
                    direction="neutral",
                    weight="medium",
                    detail="Cinq derniers matchs disponibles pour les deux clubs (mock).",
                    quality=q,
                ),
                PredictionFactor(
                    id="f3",
                    label="Compositions",
                    direction="neutral",
                    weight="low",
                    detail="Les compositions officielles ne sont pas dans le jeu de données.",
                    quality=unavailable(clock),
                ),
            ],
            quality=quality(clock, observed_at=clock.iso_shift(minutes=-90)),
        ),
        "pred_riverside_oakmont": PredictionDetail(
            id="pred_riverside_oakmont",
            match_id="mth_riverside_oakmont",
            market="1x2",
            model_family="ensemble",
            model_version="fb-ens-2026.08.1",
            calibrator_version="beta-mc-2026.08.1",
            feature_set_version="fb-pit-14",
            cutoff_at=clock.shift(minutes=-20),
            confidence="medium",
            outcomes=[
                _outcome(clock, "home", "Riverside United", 0.39, 0.38),
                _outcome(clock, "draw", "Nul", 0.28, 0.29),
                _outcome(clock, "away", "Oakmont City", 0.33, 0.33),
            ],
            factors=[
                PredictionFactor(
                    id="f4",
                    label="Rythme live",
                    direction="away",
                    weight="medium",
                    detail="Les indicateurs live sont partiels : tirs cadrés uniquement.",
                    quality=quality(clock, availability="partial", note="xG live indisponible."),
                )
            ],
            quality=quality(
                clock,
                availability="partial",
                note="Statistiques live incomplètes.",
            ),
        ),
        "pred_silverpark_westbridge": PredictionDetail(
            id="pred_silverpark_westbridge",
            match_id="mth_silverpark_westbridge",
            market="1x2",
            model_family="ensemble",
            model_version="fb-ens-2026.08.1",
            calibrator_version="beta-mc-2026.08.1",
            feature_set_version="fb-pit-14",
            cutoff_at=clock.shift(hours=-6),
            confidence="medium",
            outcomes=[
                _outcome(clock, "home", "Silverpark", 0.44, 0.43),
                _outcome(clock, "draw", "Nul", 0.3, 0.31),
                _outcome(clock, "away", "Westbridge", 0.26, 0.26),
            ],
            factors=[],
            quality=quality(clock, freshness="acceptable"),
        ),
        "pred_calder_eastmere": PredictionDetail(
            id="pred_calder_eastmere",
            match_id="mth_calder_eastmere",
            market="1x2",
            model_family="poisson",
            model_version="fb-pois-2026.07.4",
            calibrator_version="beta-mc-2026.08.1",
            feature_set_version="fb-pit-14",
            cutoff_at=clock.shift(hours=-2),
            confidence="low",
            outcomes=[
                _outcome(clock, "home", "Calder Rovers", 0.36, 0.35),
                _outcome(clock, "draw", "Nul", 0.32, 0.33),
                _outcome(clock, "away", "Eastmere", 0.32, 0.32),
            ],
            factors=[
                PredictionFactor(
                    id="f5",
                    label="Volume d'observations",
                    direction="neutral",
                    weight="high",
                    detail="Échantillon ligue 2 plus réduit : confiance abaissée (mock).",
                    quality=q,
                )
            ],
            quality=q,
        ),
        "pred_helix_meridian": PredictionDetail(
            id="pred_helix_meridian",
            match_id="mth_helix_meridian",
            market="moneyline",
            model_family="elo",
            model_version="bb-elo-2026.06.2",
            calibrator_version="platt-2026.06.2",
            feature_set_version="bb-pit-3",
            cutoff_at=clock.shift(hours=-3),
            confidence="medium",
            outcomes=[
                _outcome(clock, "home", "Helix City", 0.58, 0.56),
                _outcome(clock, "away", "Meridian", 0.42, 0.44),
            ],
            factors=[
                PredictionFactor(
                    id="f6",
                    label="Pace domicile",
                    direction="home",
                    weight="medium",
                    detail="Rythme domicile Helix au-dessus de la médiane de ligue (mock).",
                    quality=q,
                )
            ],
            quality=q,
        ),
        "pred_voss_elian": PredictionDetail(
            id="pred_voss_elian",
            match_id="mth_voss_elian",
            market="winner",
            model_family="surface_elo",
            model_version="tn-selo-2026.05.1",
            calibrator_version="platt-2026.05.1",
            feature_set_version="tn-pit-2",
            cutoff_at=clock.shift(hours=-5),
            confidence="high",
            outcomes=[
                _outcome(clock, "home", "Lena Voss", 0.62, 0.61),
                _outcome(clock, "away", "Marco Elian", 0.38, 0.39),
            ],
            factors=[
                PredictionFactor(
                    id="f7",
                    label="Elo dur",
                    direction="home",
                    weight="high",
                    detail="Avantage surface dure pour Voss sur le jeu mock.",
                    quality=q,
                )
            ],
            quality=q,
        ),
    }

    odds = {
        "odds_northgate_harbor": _odds(
            clock,
            "odds_northgate_harbor",
            "mth_northgate_harbor",
            "1x2",
            clock.iso_shift(minutes=-12),
            "fresh",
            [("home", "Northgate FC", 2.2), ("draw", "Nul", 3.4), ("away", "Harbor Athletic", 3.5)],
        ),
        "odds_riverside_oakmont": _odds(
            clock,
            "odds_riverside_oakmont",
            "mth_riverside_oakmont",
            "1x2",
            clock.iso_shift(minutes=-2),
            "fresh",
            [
                ("home", "Riverside United", 2.55),
                ("draw", "Nul", 3.2),
                ("away", "Oakmont City", 2.85),
            ],
        ),
        "odds_silverpark_westbridge": _odds(
            clock,
            "odds_silverpark_westbridge",
            "mth_silverpark_westbridge",
            "1x2",
            clock.iso_shift(hours=-8),
            "stale",
            [("home", "Silverpark", 2.05), ("draw", "Nul", 3.45), ("away", "Westbridge", 3.8)],
            "Cote observée il y a plus de 8 h. Traiter comme stale.",
        ),
        "odds_helix_meridian": _odds(
            clock,
            "odds_helix_meridian",
            "mth_helix_meridian",
            "moneyline",
            clock.iso_shift(minutes=-25),
            "fresh",
            [("home", "Helix City", 1.72), ("away", "Meridian", 2.18)],
        ),
        "odds_voss_elian": _odds(
            clock,
            "odds_voss_elian",
            "mth_voss_elian",
            "winner",
            clock.iso_shift(minutes=-40),
            "fresh",
            [("home", "Lena Voss", 1.55), ("away", "Marco Elian", 2.55)],
        ),
    }

    league_by_id = {item.id: item for item in leagues}
    team_by_id = {item.id: item for item in teams}

    matches = [
        _match(
            clock,
            league_by_id,
            team_by_id,
            predictions,
            odds,
            id="mth_northgate_harbor",
            sport="football",
            league_id="lg_continental",
            home_id="tm_northgate",
            away_id="tm_harbor",
            kickoff_hours=3,
            status="scheduled",
            venue="Northgate Park (fictif)",
            score=_score(clock, None, None, False),
            prediction_id="pred_northgate_harbor",
            odds_id="odds_northgate_harbor",
            events=[],
            stats=_football_stats(clock, None, None, False),
            form=[
                _form(clock, "tm_northgate", ["W", "W", "D", "W", "L"]),
                _form(clock, "tm_harbor", ["D", "W", "L", "W", "D"]),
            ],
            missing=[UnavailableField(field="lineups", reason="Compositions non fournies par le jeu mock.")],
        ),
        _match(
            clock,
            league_by_id,
            team_by_id,
            predictions,
            odds,
            id="mth_riverside_oakmont",
            sport="football",
            league_id="lg_continental",
            home_id="tm_riverside",
            away_id="tm_oakmont",
            kickoff_hours=0,
            kickoff_minutes=-38,
            status="live",
            venue="Riverside Lane (fictif)",
            score=_score(clock, 1, 1, True),
            prediction_id="pred_riverside_oakmont",
            odds_id="odds_riverside_oakmont",
            events=[
                _event(clock, "evt1", 12, "goal", "But Riverside", "tm_riverside"),
                _event(clock, "evt2", 31, "goal", "But Oakmont", "tm_oakmont"),
            ],
            stats=_football_stats(clock, 7, 6, True, True),
            form=[
                _form(clock, "tm_riverside", ["L", "D", "W", "D", "W"]),
                _form(clock, "tm_oakmont", ["W", "W", "D", "L", "W"]),
            ],
            missing=[
                UnavailableField(
                    field="expected_goals",
                    reason="xG live indisponible dans ce scénario partiel.",
                )
            ],
        ),
        _match(
            clock,
            league_by_id,
            team_by_id,
            predictions,
            odds,
            id="mth_silverpark_westbridge",
            sport="football",
            league_id="lg_continental",
            home_id="tm_silverpark",
            away_id="tm_westbridge",
            kickoff_hours=6,
            status="scheduled",
            venue="Silverpark Arena (fictif)",
            score=_score(clock, None, None, False),
            prediction_id="pred_silverpark_westbridge",
            odds_id="odds_silverpark_westbridge",
            events=[],
            stats=_football_stats(clock, None, None, False),
            form=[
                _form(clock, "tm_silverpark", ["D", "D", "W", "L", "D"]),
                _form(clock, "tm_westbridge", ["L", "W", "L", "D", "W"]),
            ],
            missing=[],
        ),
        _match(
            clock,
            league_by_id,
            team_by_id,
            predictions,
            odds,
            id="mth_calder_eastmere",
            sport="football",
            league_id="lg_northern",
            home_id="tm_calder",
            away_id="tm_eastmere",
            kickoff_hours=26,
            status="scheduled",
            venue="Calder Ground (fictif)",
            score=_score(clock, None, None, False),
            prediction_id="pred_calder_eastmere",
            odds_id=None,
            events=[],
            stats=_football_stats(clock, None, None, False),
            form=[
                _form(clock, "tm_calder", ["W", "L", "W", "W", "D"]),
                _form(clock, "tm_eastmere", ["D", "D", "L", "W", "L"]),
            ],
            missing=[UnavailableField(field="odds", reason="Aucune cote observée pour ce match mock.")],
        ),
        _match(
            clock,
            league_by_id,
            team_by_id,
            predictions,
            odds,
            id="mth_helix_meridian",
            sport="basketball",
            league_id="lg_metro",
            home_id="tm_helix",
            away_id="tm_meridian",
            kickoff_hours=5,
            status="scheduled",
            venue="Helix Garden (fictif)",
            score=_score(clock, None, None, False),
            prediction_id="pred_helix_meridian",
            odds_id="odds_helix_meridian",
            events=[],
            stats=[],
            form=[
                _form(clock, "tm_helix", ["W", "W", "L", "W", "W"]),
                _form(clock, "tm_meridian", ["L", "W", "W", "L", "D"]),
            ],
            missing=[
                UnavailableField(
                    field="player_availability",
                    reason="Disponibilité joueurs non fournie.",
                )
            ],
        ),
        _match(
            clock,
            league_by_id,
            team_by_id,
            predictions,
            odds,
            id="mth_voss_elian",
            sport="tennis",
            league_id="lg_grand_court",
            home_id="tm_voss",
            away_id="tm_elian",
            kickoff_hours=8,
            status="scheduled",
            venue="Court Central, Open de Meridia (fictif)",
            score=_score(clock, None, None, False),
            prediction_id="pred_voss_elian",
            odds_id="odds_voss_elian",
            events=[],
            stats=[],
            form=[
                _form(clock, "tm_voss", ["W", "W", "W", "L", "W"]),
                _form(clock, "tm_elian", ["W", "L", "W", "W", "L"]),
            ],
            missing=[],
        ),
        _match(
            clock,
            league_by_id,
            team_by_id,
            predictions,
            odds,
            id="mth_finished_demo",
            sport="football",
            league_id="lg_continental",
            home_id="tm_oakmont",
            away_id="tm_silverpark",
            kickoff_hours=-20,
            status="finished",
            venue="Oakmont Road (fictif)",
            score=_score(clock, 2, 0, True),
            prediction_id=None,
            odds_id=None,
            events=[
                _event(clock, "evt3", 41, "goal", "But Oakmont", "tm_oakmont"),
                _event(clock, "evt4", 77, "goal", "But Oakmont", "tm_oakmont"),
            ],
            stats=_football_stats(clock, 12, 4, True),
            form=[],
            missing=[
                UnavailableField(
                    field="prediction",
                    reason="Prédiction non conservée pour ce match historique mock.",
                )
            ],
        ),
        _match(
            clock,
            league_by_id,
            team_by_id,
            predictions,
            odds,
            id="mth_postponed",
            sport="football",
            league_id="lg_northern",
            home_id="tm_eastmere",
            away_id="tm_calder",
            kickoff_hours=4,
            status="postponed",
            venue="Eastmere Vale (fictif)",
            score=_score(clock, None, None, False),
            prediction_id=None,
            odds_id=None,
            events=[],
            stats=_football_stats(clock, None, None, False),
            form=[],
            missing=[
                UnavailableField(field="prediction", reason="Match reporté : aucune prédiction publiée."),
                UnavailableField(field="odds", reason="Marché retiré dans le jeu mock."),
            ],
        ),
    ]

    insights = [
        Insight(
            id="ins_1",
            title="Calibration football stable",
            body=(
                "Sur la fenêtre mock des 30 derniers jours, l'ECE du champion football reste sous 0,04. "
                "Ce n'est pas une garantie de résultat."
            ),
            kind="model",
            href="/performance",
            quality=q,
        ),
        Insight(
            id="ins_2",
            title="Cotes Silverpark anciennes",
            body="Le snapshot Atlas pour Silverpark–Westbridge a plus de 8 h. L'edge affiché est marqué stale.",
            kind="caution",
            href="/value",
            quality=quality(clock, availability="stale", freshness="stale"),
        ),
        Insight(
            id="ins_3",
            title="xG live indisponible",
            body="Le match Riverside–Oakmont n'expose que les tirs. Les xG ne doivent pas être interpolés.",
            kind="data",
            href="/matches/mth_riverside_oakmont",
            quality=quality(clock, availability="partial"),
        ),
    ]
    performance = PerformanceReport(
        summary=ModelHealthSummary(
            model_version="fb-ens-2026.08.1",
            sport="football",
            window_label="Walk-forward 90 jours (mock)",
            accuracy=0.512,
            log_loss=0.981,
            brier_score=0.238,
            ece=0.031,
            theoretical_roi=0.027,
            theoretical_max_drawdown=-0.084,
            prediction_count=640,
            quality=quality(
                clock,
                note="Métriques de backtest fictives, non issues d'un modèle entraîné.",
            ),
        ),
        series=[
            PerformanceSeriesPoint(
                period="Juin", log_loss=1.02, brier_score=0.249, accuracy=0.49, theoretical_roi=-0.012
            ),
            PerformanceSeriesPoint(
                period="Juil.", log_loss=0.996, brier_score=0.241, accuracy=0.504, theoretical_roi=0.008
            ),
            PerformanceSeriesPoint(
                period="Août", log_loss=0.972, brier_score=0.234, accuracy=0.518, theoretical_roi=0.041
            ),
            PerformanceSeriesPoint(
                period="Sept.", log_loss=0.981, brier_score=0.238, accuracy=0.512, theoretical_roi=0.027
            ),
        ],
        calibration=[
            CalibrationBucket(predicted=0.2, observed=0.18, count=72),
            CalibrationBucket(predicted=0.35, observed=0.33, count=118),
            CalibrationBucket(predicted=0.5, observed=0.48, count=164),
            CalibrationBucket(predicted=0.65, observed=0.62, count=141),
            CalibrationBucket(predicted=0.8, observed=0.77, count=88),
        ],
        notes=[
            "Le ROI est théorique : il suppose des mises unitaires au cutoff, sans frais ni limites.",
            "Les splits sont temporels. Aucun tirage aléatoire n'a été utilisé pour ces chiffres mock.",
            "Accuracy seule ne suffit pas à juger le modèle.",
        ],
    )

    return FixtureStore(
        sports=sports,
        leagues=leagues,
        teams=teams,
        players=players,
        matches=matches,
        picks=[],  # assigned by attach_picks
        insights=insights,
        performance=performance,
    )


def attach_picks(store: FixtureStore, clock: Clock, summaries: dict[str, MatchSummary]) -> None:
    store.picks = [
        Pick(
            id="pick_northgate_home",
            match=summaries["mth_northgate_harbor"],
            market="1x2",
            selection="home",
            selection_label="Northgate FC",
            calibrated_probability=0.47,
            confidence="high",
            rationale=(
                "Le pick repose sur la probabilité calibrée 47 % pour Northgate, "
                "supérieure au seuil interne de publication. Ce n'est pas une recommandation de mise."
            ),
            criteria="Probabilité calibrée ≥ 45 %, confiance élevée, cutoff respecté.",
            model_version="fb-ens-2026.08.1",
            published_at=clock.shift(minutes=-80),
            quality=quality(clock, observed_at=clock.iso_shift(minutes=-80)),
        ),
        Pick(
            id="pick_voss",
            match=summaries["mth_voss_elian"],
            market="winner",
            selection="home",
            selection_label="Lena Voss",
            calibrated_probability=0.61,
            confidence="high",
            rationale=(
                "Signal surface dure : Elo dur mock en faveur de Voss. Les blessures ne sont pas dans le fact pack."
            ),
            criteria="Confiance élevée et marché binaire tennis.",
            model_version="tn-selo-2026.05.1",
            published_at=clock.shift(minutes=-70),
            quality=quality(clock, observed_at=clock.iso_shift(minutes=-70)),
        ),
        Pick(
            id="pick_helix",
            match=summaries["mth_helix_meridian"],
            market="moneyline",
            selection="home",
            selection_label="Helix City",
            calibrated_probability=0.56,
            confidence="medium",
            rationale=(
                "Probabilité calibrée 56 % pour Helix. La disponibilité des joueurs est indisponible : "
                "le pick reste un signal de modèle, pas une certitude."
            ),
            criteria="Confiance moyenne acceptée si le marché est couvert et le cutoff valide.",
            model_version="bb-elo-2026.06.2",
            published_at=clock.shift(minutes=-50),
            quality=quality(clock, observed_at=clock.iso_shift(minutes=-50)),
        ),
    ]


def _team(id: str, name: str, short_name: str, abbreviation: str, sport: SportCode, league_id: str) -> Team:
    return Team(
        id=id,
        name=name,
        short_name=short_name,
        sport=sport,
        league_id=league_id,
        abbreviation=abbreviation,
    )


def _outcome(clock: Clock, selection: str, label: str, model: float, calibrated: float) -> ProbabilityOutcome:
    return ProbabilityOutcome(
        selection=selection,
        label=label,
        model_probability=model,
        calibrated_probability=calibrated,
        quality=quality(clock),
    )


def _odds(
    clock: Clock,
    id: str,
    match_id: str,
    market: str,
    observed_at: str,
    freshness: FreshnessLevel,
    selections: Sequence[tuple[str, str, float]],
    note: str | None = None,
) -> OddsSnapshot:
    from app.core.clock import parse_rfc3339

    market_odds = [row[2] for row in selections]
    overround = float(calculator.overround(market_odds))
    items = [
        OddsSelection(
            selection=selection,
            label=label,
            decimal_odds=odds,
            implied_probability_raw=float(calculator.implied_probability(odds)),
            no_vig_probability=float(calculator.no_vig_probability(odds, market_odds)),
            quality=quality(clock, source="mock.bookmaker.atlas"),
        )
        for selection, label, odds in selections
    ]
    return OddsSnapshot(
        id=id,
        match_id=match_id,
        market=market,
        bookmaker="Atlas (fictif)",
        provider="mock.odds.atlas",
        observed_at=parse_rfc3339(observed_at),
        overround=overround,
        selections=items,
        quality=quality(
            clock,
            source="mock.odds.atlas",
            observed_at=observed_at,
            freshness=freshness,
            availability="stale" if freshness == "stale" else "available",
            note=note,
        ),
    )


def _score(clock: Clock, home: int | None, away: int | None, available: bool) -> Scoreline:
    return Scoreline(
        home=home,
        away=away,
        quality=quality(clock) if available else unavailable(clock),
    )


def _form(clock: Clock, team_id: str, results: list[FormResult]) -> TeamFormSide:
    return TeamFormSide(
        team_id=team_id,
        results=results,
        quality=quality(clock),
    )


def _event(clock: Clock, id: str, minute: int, type_: str, label: str, team_id: str) -> MatchEvent:
    return MatchEvent(
        id=id,
        minute=minute,
        type=type_,
        label=label,
        team_id=team_id,
        quality=quality(clock),
    )


def _football_stats(
    clock: Clock,
    home_shots: float | None,
    away_shots: float | None,
    available: bool,
    partial: bool = False,
) -> list[MatchStatistic]:
    q = (
        quality(
            clock,
            availability="partial" if partial else "available",
            note="xG et possession live indisponibles." if partial else None,
        )
        if available
        else unavailable(clock)
    )
    return [
        MatchStatistic(
            key="shots",
            label="Tirs",
            home_value=home_shots,
            away_value=away_shots,
            unit="count",
            quality=q,
        ),
        MatchStatistic(
            key="xg",
            label="xG",
            home_value=None,
            away_value=None,
            unit="expected_goals",
            quality=unavailable(clock),
        ),
    ]


def _match(
    clock: Clock,
    leagues: dict[str, League],
    teams: dict[str, Team],
    predictions: dict[str, PredictionDetail],
    odds: dict[str, OddsSnapshot],
    *,
    id: str,
    sport: SportCode,
    league_id: str,
    home_id: str,
    away_id: str,
    kickoff_hours: int,
    status: MatchStatus,
    venue: str,
    score: Scoreline,
    prediction_id: str | None,
    odds_id: str | None,
    events: list[MatchEvent],
    stats: list[MatchStatistic],
    form: list[TeamFormSide],
    missing: list[UnavailableField],
    kickoff_minutes: int = 0,
) -> MatchDetail:
    prediction = predictions.get(prediction_id) if prediction_id else None
    odds_snap = odds.get(odds_id) if odds_id else None
    freshness: FreshnessLevel = "stale" if odds_snap and odds_snap.quality.freshness == "stale" else "fresh"
    availability: AvailabilityStatus = "unavailable" if status == "postponed" else "available"
    return MatchDetail(
        id=id,
        sport=sport,
        league=leagues[league_id],
        home=teams[home_id],
        away=teams[away_id],
        kickoff_at=clock.shift(hours=kickoff_hours, minutes=kickoff_minutes),
        status=status,
        venue=venue,
        score=score,
        prediction_preview=None,
        value_preview=None,
        quality=quality(
            clock,
            availability=availability,
            freshness=freshness,
        ),
        timeline=events,
        stats=stats,
        odds=odds_snap,
        prediction=prediction,
        form=form,
        unavailable_fields=missing,
    )
