from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.core.config import Settings
from app.db.models import Base
from app.db.models import League as LeagueRow
from app.db.models import Match as MatchRow
from app.db.models import Player as PlayerRow
from app.db.models import Sport as SportRow
from app.db.models import Team as TeamRow
from app.db.session import reset_database_state
from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session, sessionmaker
from tests.conftest import TestSettings

NOW = datetime(2026, 9, 12, 15, 0, tzinfo=UTC)
LIVE_MATCH_ID = "mth_catalog_live_001"
MOCK_MATCH_ID = "mth_catalog_mock_hidden"
FORBIDDEN_FIXTURE_IDS = ("mth_helix_meridian", "mth_northgate_harbor")


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(type_: JSONB, compiler: object, **_: object) -> str:
    return "JSON"


def sqlite_url(path: Path) -> str:
    return f"sqlite+pysqlite:///{path.resolve()}"


def create_catalog_database(path: Path, *, seed: bool = False) -> str:
    url = sqlite_url(path)
    engine = create_engine(url, future=True)
    Base.metadata.create_all(engine)
    if seed:
        factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
        with factory() as session:
            _seed_catalog(session)
            session.commit()
    engine.dispose()
    reset_database_state()
    return url


def sql_settings(database_url: str, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "env": "test",
        "data_mode": "live",
        "repository": "sql",
        "log_level": "WARNING",
        "database_url": database_url,
        "cors_origins": ["http://localhost:3000"],
        "mock_now": "2026-09-09T18:00:00Z",
    }
    values.update(overrides)
    return TestSettings(**values)  # type: ignore[arg-type]


def _seed_catalog(session: Session) -> None:
    sport = SportRow(id="spt_football", code="football", name="Football", created_at=NOW)
    league = LeagueRow(
        id="lg_catalog_premier",
        sport_id=sport.id,
        name="Catalog Premier",
        country="England",
        season="2026",
        tier=1,
        created_at=NOW,
    )
    home = TeamRow(
        id="tm_catalog_alpha",
        sport_id=sport.id,
        league_id=league.id,
        name="Catalog Alpha",
        short_name="Alpha",
        abbreviation="ALP",
        created_at=NOW,
    )
    away = TeamRow(
        id="tm_catalog_beta",
        sport_id=sport.id,
        league_id=league.id,
        name="Catalog Beta",
        short_name="Beta",
        abbreviation="BET",
        created_at=NOW,
    )
    player = PlayerRow(
        id="pl_catalog_keeper",
        sport_id=sport.id,
        team_id=home.id,
        name="Catalog Keeper",
        position="GK",
        country="England",
        created_at=NOW,
    )
    live_match = MatchRow(
        id=LIVE_MATCH_ID,
        sport_id=sport.id,
        league_id=league.id,
        home_team_id=home.id,
        away_team_id=away.id,
        kickoff_at=NOW,
        status="scheduled",
        venue="Catalog Arena",
        home_score=None,
        away_score=None,
        source="sportmonks",
        collected_at=NOW,
        available_at=NOW,
        data_mode="live",
        created_at=NOW,
        updated_at=NOW,
    )
    mock_match = MatchRow(
        id=MOCK_MATCH_ID,
        sport_id=sport.id,
        league_id=league.id,
        home_team_id=home.id,
        away_team_id=away.id,
        kickoff_at=NOW,
        status="scheduled",
        venue="Mock Pitch",
        home_score=0,
        away_score=0,
        source="mock.fixtures.v1",
        collected_at=NOW,
        available_at=NOW,
        data_mode="mock",
        created_at=NOW,
        updated_at=NOW,
    )
    finished = MatchRow(
        id="mth_catalog_finished_002",
        sport_id=sport.id,
        league_id=league.id,
        home_team_id=home.id,
        away_team_id=away.id,
        kickoff_at=datetime(2026, 9, 11, 15, 0, tzinfo=UTC),
        status="finished",
        venue="Catalog Arena",
        home_score=2,
        away_score=1,
        source="sportmonks",
        collected_at=NOW,
        available_at=NOW,
        data_mode="live",
        created_at=NOW,
        updated_at=NOW,
    )
    session.add_all([sport, league, home, away, player, live_match, mock_match, finished])
