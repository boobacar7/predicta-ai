from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest
from app.ai_picks.config import AI_PICKS_VERSION
from app.backtesting.production_oos import persisted_score_path, quotes_from_persisted_analytical
from app.backtesting.production_oos_sql import (
    JSON_ODDS_SOURCE,
    ODDS_REPOSITORY_NAME,
    ODDS_SOURCE_SQL,
    MatchCutoff,
    SqlOddsUnavailableError,
    compare_prediction_parity,
    load_live_sql_pit_quotes,
    synthetic_future_quote,
)
from app.odds.providers import MOCK_ODDS_SOURCE, LiveOddsProvider
from app.odds.repository import InMemoryOddsRepository
from app.odds.service import OddsService
from app.odds.the_odds_api import LIVE_ODDS_SOURCE
from app.odds.types import DataMode, Football1x2Selection, OddsSelection, OddsSnapshot
from app.predictions.runtime import repository_root
from app.value_engine.calculator import VALUE_ENGINE_VERSION
from predicta_ml.oos.ai_picks import published_thresholds
from predicta_ml.oos.odds import select_pit_snapshot
from predicta_ml.oos.protocol import VALUE_ENGINE_VERSION as OOS_VALUE_ENGINE_VERSION

KICKOFF = datetime(2026, 8, 22, 15, tzinfo=UTC)
MATCH_ID = "mth_football-sportmonks-oos-sql"


class RecordingSqlRepository:
    def __init__(self, snapshots: tuple[OddsSnapshot, ...], *, fail: Exception | None = None) -> None:
        self.snapshots = snapshots
        self.fail = fail
        self.calls: list[dict[str, object]] = []

    def history_many(
        self,
        match_ids: Sequence[str],
        market: str,
        *,
        source: str | None = None,
        data_mode: DataMode | None = None,
    ) -> tuple[OddsSnapshot, ...]:
        self.calls.append(
            {
                "match_ids": list(match_ids),
                "market": market,
                "source": source,
                "data_mode": data_mode,
            }
        )
        if self.fail is not None:
            raise self.fail
        return tuple(
            item
            for item in self.snapshots
            if item.match_id in set(match_ids) and item.market == market
        )


def _snapshot(
    *,
    snapshot_id: str,
    match_id: str = MATCH_ID,
    available_at: datetime,
    home: str = "2.10",
    draw: str = "3.40",
    away: str = "3.60",
    source: str = LIVE_ODDS_SOURCE,
    data_mode: DataMode = "live",
    bookmaker: str = "book-a",
) -> OddsSnapshot:
    return OddsSnapshot(
        id=snapshot_id,
        provider_id=snapshot_id,
        match_id=match_id,
        bookmaker=bookmaker,
        market="1X2",
        selections=(
            OddsSelection(Football1x2Selection.HOME, Decimal(home)),
            OddsSelection(Football1x2Selection.DRAW, Decimal(draw)),
            OddsSelection(Football1x2Selection.AWAY, Decimal(away)),
        ),
        collected_at=available_at,
        available_at=available_at,
        source=source,
        data_mode=data_mode,
        raw_payload_id="raw-sql-1",
    )


def _cutoff(match_id: str = MATCH_ID) -> MatchCutoff:
    return MatchCutoff(match_id=match_id, cutoff_at=KICKOFF, kickoff_at=KICKOFF)


def test_sql_loader_uses_history_many_and_not_json(monkeypatch: pytest.MonkeyPatch) -> None:
    pit = _snapshot(snapshot_id="pit", available_at=KICKOFF - timedelta(hours=2), home="2.20")
    later = _snapshot(snapshot_id="later", available_at=KICKOFF - timedelta(minutes=20), home="2.05")
    repo = RecordingSqlRepository((pit, later))

    def _forbidden(_path: Path) -> tuple[object, ...]:
        raise AssertionError("JSON odds fixture must not be read for the live SQL OOS rerun.")

    monkeypatch.setattr(
        "app.backtesting.production_oos.quotes_from_persisted_analytical",
        _forbidden,
    )
    isolation = load_live_sql_pit_quotes(repo, (_cutoff(),))
    assert repo.calls
    assert repo.calls[0]["source"] == LIVE_ODDS_SOURCE
    assert repo.calls[0]["data_mode"] == "live"
    assert repo.calls[0]["market"] == "1X2"
    assert isolation.odds_source == ODDS_SOURCE_SQL
    assert isolation.repository == ODDS_REPOSITORY_NAME
    assert isolation.mock_odds_used == 0
    assert isolation.live_odds_used == 1
    assert isolation.quotes[0].snapshot_id == "later"
    assert isolation.quotes[0].data_mode == "live"
    assert isolation.quotes[0].provider == LIVE_ODDS_SOURCE
    assert JSON_ODDS_SOURCE not in isolation.odds_source
    assert persisted_score_path().name == "persisted-final-test-history-score.json"


def test_sql_unavailable_fails_without_json_fallback() -> None:
    repo = RecordingSqlRepository((), fail=RuntimeError("connection refused"))
    with pytest.raises(SqlOddsUnavailableError, match="refusing to fall back"):
        load_live_sql_pit_quotes(repo, (_cutoff(),))


def test_empty_sql_history_fails_without_json_fallback() -> None:
    repo = RecordingSqlRepository(())
    with pytest.raises(SqlOddsUnavailableError, match="zero live"):
        load_live_sql_pit_quotes(repo, (_cutoff(),))


def test_mock_odds_cannot_enter_oos() -> None:
    mock = _snapshot(
        snapshot_id="mock",
        available_at=KICKOFF - timedelta(hours=1),
        source=MOCK_ODDS_SOURCE,
        data_mode="mock",
    )
    live = _snapshot(snapshot_id="live", available_at=KICKOFF - timedelta(hours=1), home="2.20")
    with pytest.raises(SqlOddsUnavailableError, match="Mock odds"):
        load_live_sql_pit_quotes(RecordingSqlRepository((mock,)), (_cutoff(),))
    with pytest.raises(SqlOddsUnavailableError, match="Mock odds"):
        load_live_sql_pit_quotes(RecordingSqlRepository((live, mock)), (_cutoff(),))


def test_pit_cutoff_selects_last_pre_cutoff_not_future() -> None:
    pit = _snapshot(snapshot_id="pit", available_at=KICKOFF - timedelta(hours=3), home="2.40")
    later = _snapshot(snapshot_id="later", available_at=KICKOFF - timedelta(minutes=10), home="2.05")
    future = _snapshot(snapshot_id="future", available_at=KICKOFF + timedelta(minutes=5), home="1.20")
    isolation = load_live_sql_pit_quotes(RecordingSqlRepository((pit, later, future)), (_cutoff(),))
    assert isolation.quotes[0].snapshot_id == "later"
    assert isolation.quotes[0].home_odds == 2.05
    service = OddsService(
        provider=LiveOddsProvider(enable_live=True, snapshots=(pit, later, future)),
        repository=InMemoryOddsRepository(),
    )
    selected = service.market_at(match_id=MATCH_ID, market="1X2", cutoff_at=KICKOFF)
    assert selected.id == "later"


def test_future_odds_do_not_change_selected_sql_quote() -> None:
    pit = _snapshot(snapshot_id="pit", available_at=KICKOFF - timedelta(hours=1), home="2.30")
    isolation = load_live_sql_pit_quotes(RecordingSqlRepository((pit,)), (_cutoff(),))
    future = synthetic_future_quote(isolation.quotes[0])
    selected = select_pit_snapshot(
        isolation.quotes + (future,),
        match_id=MATCH_ID,
        cutoff_at=KICKOFF,
        kickoff_at=KICKOFF,
    )
    assert selected.snapshot_id == "pit"
    assert selected.home_odds != 1.01


def test_colliding_bookmaker_timestamps_use_snapshot_id_tiebreak() -> None:
    stamp = KICKOFF - timedelta(hours=1)
    first = _snapshot(snapshot_id="book-a", available_at=stamp, home="2.10", bookmaker="book-a")
    second = _snapshot(snapshot_id="book-b", available_at=stamp, home="1.90", bookmaker="book-b")
    isolation = load_live_sql_pit_quotes(RecordingSqlRepository((first, second)), (_cutoff(),))
    assert isolation.live_snapshots_considered == 2
    assert isolation.live_snapshots_eligible == 2
    assert isolation.live_snapshots_selected == 1
    assert isolation.quotes[0].snapshot_id == "book-b"
    assert isolation.quotes[0].home_odds == 1.90


def test_prediction_parity_is_exact() -> None:
    previous = {"m1": (0.41, 0.27, 0.32), "m2": (0.50, 0.25, 0.25)}
    current = {"m1": (0.41, 0.27, 0.32), "m2": (0.50, 0.25, 0.25)}
    parity = compare_prediction_parity(
        previous,
        current,
        model_version="football-elo-v1-candidate",
        dataset_version="football-1x2-history-0.3",
        feature_schema="football-1x2-features-0.3",
    )
    assert parity["passed"] is True
    assert parity["n_differences"] == 0
    changed = compare_prediction_parity(
        previous,
        {"m1": (0.99, 0.005, 0.005), "m2": (0.50, 0.25, 0.25)},
        model_version="football-elo-v1-candidate",
        dataset_version="football-1x2-history-0.3",
        feature_schema="football-1x2-features-0.3",
    )
    assert changed["passed"] is False
    assert changed["n_differences"] == 1


def test_value_engine_and_ai_picks_remain_frozen() -> None:
    assert VALUE_ENGINE_VERSION == OOS_VALUE_ENGINE_VERSION == "value-engine-0.1"
    assert AI_PICKS_VERSION == "ai-picks-0.1"
    thresholds = published_thresholds()
    assert thresholds["minimum_edge"] == 0.0
    assert thresholds["minimum_ev"] == 0.0
    assert thresholds["minimum_model_probability"] == 0.0
    assert thresholds["maximum_odds_age_seconds"] == 86400
    assert thresholds["optimized_on_oos"] is False


def test_json_fixture_loader_is_not_the_sql_source() -> None:
    path = persisted_score_path()
    if path.is_file():
        quotes = quotes_from_persisted_analytical(path)
        assert all("::" in item.snapshot_id for item in quotes[:1] or quotes)
    assert ODDS_SOURCE_SQL != JSON_ODDS_SOURCE
    assert ODDS_REPOSITORY_NAME == "SqlOddsRepository"


def test_committed_live_sql_report_is_sql_only_with_prediction_parity() -> None:
    report = json.loads(
        (repository_root() / "workers" / "ml" / "reports" / "production-oos-backtest-live-sql.json").read_text(
            encoding="utf-8"
        )
    )
    parity = json.loads(
        (repository_root() / "workers" / "ml" / "reports" / "prediction_parity.json").read_text(encoding="utf-8")
    )
    assert report["odds_source"] == ODDS_SOURCE_SQL
    assert report["odds_repository"] == ODDS_REPOSITORY_NAME
    assert report["json_odds_source_used"] is False
    assert report["new_api_credits"] == 0
    assert report["odds_isolation"]["mock_odds_used"] == 0
    assert report["odds_isolation"]["live_odds_used"] > 0
    assert report["odds_isolation"]["provider"] == LIVE_ODDS_SOURCE
    assert report["prediction_parity"]["n_differences"] == 0
    assert parity["n_differences"] == 0
    assert parity["passed"] is True
    assert report["candidate_promoted"] is False
    assert report["ai_picks"]["thresholds"]["optimized_on_oos"] is False
    assert report["odds"]["n_matches"] == 387
    assert report["ai_picks"]["n_picks"] != report["odds"]["n_matches_with_odds"]
