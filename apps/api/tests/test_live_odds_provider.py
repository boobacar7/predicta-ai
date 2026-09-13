from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from app.core.clock import Clock
from app.odds.exceptions import IncompleteOddsMarketError, OddsTemporalLeakageError, OddsUnavailableError
from app.odds.providers import LIVE_ODDS_SOURCE, LiveOddsProvider, MockOddsProvider
from app.odds.repository import InMemoryOddsRepository
from app.odds.service import OddsService
from app.odds.the_odds_api import football_1x2_selection, map_the_odds_api_events
from app.odds.types import Football1x2Selection, OddsSelection, OddsSnapshot
from app.value_engine.calculator import edge, expected_value, implied_probability, overround
from app.value_engine.service import FootballValueService
from tests.test_odds_value_engine_v01 import StaticPredictionService, snapshot

MATCH_ID = "match_live_odds"
CUTOFF = datetime(2026, 9, 8, 18, tzinfo=UTC)


LIVE_EVENT = {
    "id": "epl_helix_meridian_20260908",
    "home_team": "Helix FC",
    "away_team": "Meridian Athletic",
    "bookmakers": [
        {
            "key": "pinnacle",
            "last_update": "2026-09-08T16:00:00Z",
            "markets": [
                {
                    "key": "h2h",
                    "outcomes": [
                        {"name": "Helix FC", "price": 2.00},
                        {"name": "Draw", "price": 4.00},
                        {"name": "Meridian Athletic", "price": 5.00},
                    ],
                }
            ],
        }
    ],
}


def _live_snapshot(
    *,
    snapshot_id: str = "odd_live_1",
    available_at: datetime = datetime(2026, 9, 8, 16, tzinfo=UTC),
    home: Decimal = Decimal("2.00"),
    selections: tuple[OddsSelection, ...] | None = None,
    bookmaker: str = "pinnacle",
) -> OddsSnapshot:
    return OddsSnapshot(
        id=snapshot_id,
        provider_id=snapshot_id,
        match_id=MATCH_ID,
        bookmaker=bookmaker,
        market="1X2",
        selections=selections
        or (
            OddsSelection(Football1x2Selection.HOME, home),
            OddsSelection(Football1x2Selection.DRAW, Decimal("4.00")),
            OddsSelection(Football1x2Selection.AWAY, Decimal("5.00")),
        ),
        collected_at=available_at,
        available_at=available_at,
        source=LIVE_ODDS_SOURCE,
        data_mode="live",
        raw_payload_id="raw_live_1",
    )


def test_mock_provider_still_serves_fixtures() -> None:
    provider = MockOddsProvider()
    fetched = provider.fetch("mth_football-sportmonks-19719892", "1X2")
    assert fetched
    assert provider.data_mode == "mock"
    assert all(item.data_mode == "mock" for item in fetched)


def test_live_without_key_is_explicit() -> None:
    live = LiveOddsProvider(enable_live=True)
    with pytest.raises(OddsUnavailableError, match="no API key"):
        live.fetch(MATCH_ID, "1X2")


def test_unconfigured_live_never_synthesizes() -> None:
    live = LiveOddsProvider()
    assert live.source == "unconfigured-live-odds-provider"
    with pytest.raises(OddsUnavailableError, match="never synthesized"):
        live.fetch(MATCH_ID, "1X2")


def test_live_http_belongs_to_ingestion_and_does_not_fallback_to_mock() -> None:
    live = LiveOddsProvider(enable_live=True, api_key="odds_test_secret_do_not_log")
    with pytest.raises(OddsUnavailableError, match="no mock fallback"):
        live.fetch(MATCH_ID, "1X2")
    service = OddsService(provider=live, repository=InMemoryOddsRepository())
    with pytest.raises(OddsUnavailableError):
        service.market_at(match_id=MATCH_ID, market="1X2", cutoff_at=CUTOFF)
    mock = MockOddsProvider()
    assert mock.fetch("mth_football-sportmonks-19719892", "1X2")


def test_live_mapped_snapshots_set_data_mode_live() -> None:
    snapshots = map_the_odds_api_events([LIVE_EVENT], match_id=MATCH_ID, market="1X2")
    assert snapshots
    assert all(item.data_mode == "live" for item in snapshots)
    assert all(item.source == LIVE_ODDS_SOURCE for item in snapshots)
    provider = LiveOddsProvider(snapshots, enable_live=True)
    fetched = provider.fetch(MATCH_ID, "1X2")
    assert fetched[0].bookmaker == "pinnacle"
    assert {item.selection for item in fetched[0].selections} == set(Football1x2Selection)


def test_mapping_does_not_invent_unknown_outcomes() -> None:
    assert football_1x2_selection("Yes", home_team="Helix FC", away_team="Meridian Athletic") is None


def test_old_and_new_snapshots_are_append_only() -> None:
    repository = InMemoryOddsRepository()
    early = _live_snapshot(snapshot_id="early", available_at=datetime(2026, 9, 8, 15, tzinfo=UTC), home=Decimal("1.80"))
    late = _live_snapshot(snapshot_id="late", available_at=datetime(2026, 9, 8, 16, tzinfo=UTC), home=Decimal("1.92"))
    provider = LiveOddsProvider((late, early), enable_live=True)
    service = OddsService(provider=provider, repository=repository)
    chosen = service.market_at(match_id=MATCH_ID, market="1X2", cutoff_at=CUTOFF)
    assert chosen.id == "late"
    history = repository.history(MATCH_ID, "1X2", source=LIVE_ODDS_SOURCE, data_mode="live")
    assert [item.id for item in history] == ["early", "late"]
    service.market_at(match_id=MATCH_ID, market="1X2", cutoff_at=CUTOFF)
    assert len(repository.history(MATCH_ID, "1X2", source=LIVE_ODDS_SOURCE, data_mode="live")) == 2


def test_incomplete_snapshot_does_not_mask_complete_older_one() -> None:
    complete = _live_snapshot(snapshot_id="complete", available_at=datetime(2026, 9, 8, 15, tzinfo=UTC))
    incomplete = _live_snapshot(
        snapshot_id="incomplete",
        available_at=datetime(2026, 9, 8, 16, tzinfo=UTC),
        selections=(
            OddsSelection(Football1x2Selection.HOME, Decimal("1.90")),
            OddsSelection(Football1x2Selection.AWAY, Decimal("4.10")),
        ),
    )
    service = OddsService(
        provider=LiveOddsProvider((incomplete, complete), enable_live=True),
        repository=InMemoryOddsRepository(),
    )
    chosen = service.market_at(match_id=MATCH_ID, market="1X2", cutoff_at=CUTOFF)
    assert chosen.id == "complete"


def test_incomplete_only_market_is_refused() -> None:
    incomplete = _live_snapshot(
        snapshot_id="only_incomplete",
        selections=(
            OddsSelection(Football1x2Selection.HOME, Decimal("1.90")),
            OddsSelection(Football1x2Selection.AWAY, Decimal("4.10")),
        ),
    )
    service = OddsService(
        provider=LiveOddsProvider((incomplete,), enable_live=True),
        repository=InMemoryOddsRepository(),
    )
    with pytest.raises(IncompleteOddsMarketError):
        service.market_at(match_id=MATCH_ID, market="1X2", cutoff_at=CUTOFF)


def test_post_cutoff_snapshot_is_temporal_leakage() -> None:
    future = _live_snapshot(available_at=datetime(2026, 9, 8, 18, 0, 1, tzinfo=UTC))
    service = OddsService(
        provider=LiveOddsProvider((future,), enable_live=True),
        repository=InMemoryOddsRepository(),
    )
    with pytest.raises(OddsTemporalLeakageError):
        service.market_at(match_id=MATCH_ID, market="1X2", cutoff_at=CUTOFF)


def test_absent_bookmaker_is_not_invented() -> None:
    snapshots = map_the_odds_api_events(
        [
            {
                "id": "evt",
                "home_team": "Helix FC",
                "away_team": "Meridian Athletic",
                "bookmakers": [
                    {
                        "key": "marathonbet",
                        "last_update": "2026-09-08T16:00:00Z",
                        "markets": [
                            {
                                "key": "h2h",
                                "outcomes": [
                                    {"name": "Helix FC", "price": 2.00},
                                    {"name": "Draw", "price": 4.00},
                                    {"name": "Meridian Athletic", "price": 5.00},
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
        match_id=MATCH_ID,
        market="1X2",
    )
    assert [item.bookmaker for item in snapshots] == ["marathonbet"]


def test_value_engine_parity_with_canonical_formulas() -> None:
    provider = LiveOddsProvider((_live_snapshot(),), enable_live=True)
    odds = OddsService(provider=provider, repository=InMemoryOddsRepository())
    value = FootballValueService(
        clock=Clock(CUTOFF),
        predictions=StaticPredictionService(),
        odds=odds,
    )
    result = value.evaluate(MATCH_ID, CUTOFF)
    assert result.market_probabilities.home.implied_probability == pytest.approx(0.50)
    assert result.value.home.edge == pytest.approx(0.10)
    assert result.value.home.ev == pytest.approx(0.20)
    assert result.metadata.data_mode == "live"
    assert result.metadata.odds_source == LIVE_ODDS_SOURCE
    assert implied_probability(Decimal("2.00")) == Decimal("0.5")
    assert overround((Decimal("2.00"), Decimal("4.00"), Decimal("5.00"))) == Decimal("0.95")
    assert edge(Decimal("0.60"), Decimal("0.5")) == Decimal("0.10")
    assert expected_value(Decimal("0.60"), Decimal("2.00")) == Decimal("0.20")


def test_live_provider_does_not_read_mock_history() -> None:
    repository = InMemoryOddsRepository()
    repository.append(snapshot())
    live = LiveOddsProvider(enable_live=True, snapshots=())
    service = OddsService(provider=live, repository=repository)
    with pytest.raises(OddsUnavailableError):
        service.market_at(match_id=snapshot().match_id, market="1X2", cutoff_at=datetime(2026, 7, 7, 16, tzinfo=UTC))
