from datetime import UTC, datetime

from app.db.models import League as LeagueRow
from app.db.models import Match as MatchRow
from app.db.models import Sport as SportRow
from app.db.models import Team as TeamRow
from app.repositories.sql_mapping import map_match, map_score, map_sport

NOW = datetime(2026, 9, 12, 15, 0, tzinfo=UTC)
FORBIDDEN_FIXTURE_IDS = ("mth_helix_meridian", "mth_northgate_harbor")


def _sport() -> SportRow:
    return SportRow(id="spt_football", code="football", name="Football", created_at=NOW)


def _league() -> LeagueRow:
    return LeagueRow(
        id="lg_catalog_premier",
        sport_id="spt_football",
        name="Catalog Premier",
        country="England",
        season="2026",
        tier=1,
        created_at=NOW,
    )


def _team(team_id: str, name: str) -> TeamRow:
    return TeamRow(
        id=team_id,
        sport_id="spt_football",
        league_id="lg_catalog_premier",
        name=name,
        short_name=name,
        abbreviation=name[:3].upper(),
        created_at=NOW,
    )


def _match(**overrides: object) -> MatchRow:
    values: dict[str, object] = {
        "id": "mth_catalog_live_001",
        "sport_id": "spt_football",
        "league_id": "lg_catalog_premier",
        "home_team_id": "tm_catalog_alpha",
        "away_team_id": "tm_catalog_beta",
        "kickoff_at": NOW,
        "status": "scheduled",
        "venue": "Catalog Arena",
        "home_score": None,
        "away_score": None,
        "source": "sportmonks",
        "collected_at": NOW,
        "available_at": NOW,
        "data_mode": "live",
        "created_at": NOW,
        "updated_at": NOW,
    }
    values.update(overrides)
    return MatchRow(**values)  # type: ignore[arg-type]


def test_map_sport_skips_unknown_codes() -> None:
    row = SportRow(id="spt_other", code="snooker", name="Snooker", created_at=NOW)
    assert map_sport(row) is None
    mapped = map_sport(_sport())
    assert mapped is not None
    assert mapped.code == "football"


def test_missing_score_is_unavailable_not_zero() -> None:
    score = map_score(_match())
    assert score.home is None
    assert score.away is None
    assert score.quality.availability == "unavailable"
    assert score.home != 0
    assert score.away != 0


def test_published_score_is_not_invented() -> None:
    score = map_score(_match(home_score=2, away_score=1, status="finished"))
    assert score.home == 2
    assert score.away == 1
    assert score.quality.availability == "available"


def test_match_mapping_marks_odds_stats_prediction_unavailable() -> None:
    detail = map_match(
        _match(),
        _sport(),
        _league(),
        _team("tm_catalog_alpha", "Catalog Alpha"),
        _team("tm_catalog_beta", "Catalog Beta"),
    )
    assert detail is not None
    assert detail.id == "mth_catalog_live_001"
    assert detail.id not in FORBIDDEN_FIXTURE_IDS
    assert detail.odds is None
    assert detail.prediction is None
    assert detail.prediction_preview is None
    assert detail.value_preview is None
    assert detail.stats == []
    assert detail.timeline == []
    assert detail.form == []
    missing = {item.field for item in detail.unavailable_fields}
    assert missing >= {"odds", "prediction", "stats", "timeline", "form"}
    assert detail.score.quality.availability == "unavailable"
    assert detail.score.home is None
