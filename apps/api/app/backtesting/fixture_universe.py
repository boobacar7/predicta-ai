from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from app.backtesting.types import CatalogMatch
from app.predictions.runtime import repository_root

FIXTURE_CLOCK = datetime(2026, 8, 16, 19, tzinfo=UTC)
LIVE_WEEKEND_START = datetime(2026, 8, 21, tzinfo=UTC)
LIVE_WEEKEND_END = datetime(2026, 8, 25, tzinfo=UTC)
LIVE_WEEKEND_CLOCK = datetime(2026, 8, 25, tzinfo=UTC)
LIVE_COMPETITIONS = frozenset({"Premier League", "Ligue 1"})

HELIX_ID = "mth_football-sportmonks-helix-pilot"
BOURNEMOUTH_ID = "mth_football-sportmonks-bournemouth-pilot"
MARSEILLE_ID = "mth_football-sportmonks-marseille-pilot"
RENNES_PSG_ID = "mth_football-sportmonks-rennes-psg-orientation"

# Synthetic labels for the committed historical-odds fixtures. They prove the
# settlement path. They are not production results and must not be sold as ROI.
FIXTURE_CATALOG: tuple[CatalogMatch, ...] = (
    CatalogMatch(
        match_id=HELIX_ID,
        home_team_id="tm_helix",
        away_team_id="tm_meridian",
        home_team="Helix FC",
        away_team="Meridian Athletic",
        league="Premier League",
        kickoff_at=datetime(2026, 8, 16, 14, tzinfo=UTC),
        outcome="HOME",
        home_elo_pre=1680.0,
        away_elo_pre=1500.0,
    ),
    CatalogMatch(
        match_id=BOURNEMOUTH_ID,
        home_team_id="tm_football-sportmonks-52",
        away_team_id="tm_football-sportmonks-brentford-pilot",
        home_team="AFC Bournemouth",
        away_team="Brentford",
        league="Premier League",
        kickoff_at=datetime(2026, 8, 16, 14, tzinfo=UTC),
        outcome="AWAY",
        home_elo_pre=1540.0,
        away_elo_pre=1580.0,
    ),
    CatalogMatch(
        match_id=MARSEILLE_ID,
        home_team_id="tm_football-sportmonks-44",
        away_team_id="tm_football-sportmonks-6789",
        home_team="Olympique Marseille",
        away_team="Monaco",
        league="Ligue 1",
        kickoff_at=datetime(2026, 8, 16, 18, 45, tzinfo=UTC),
        outcome="DRAW",
        home_elo_pre=1620.0,
        away_elo_pre=1600.0,
    ),
    CatalogMatch(
        match_id=RENNES_PSG_ID,
        home_team_id="tm_football-sportmonks-rennes",
        away_team_id="tm_football-sportmonks-psg",
        home_team="Rennes",
        away_team="Paris Saint Germain",
        league="Ligue 1",
        kickoff_at=datetime(2026, 8, 23, 18, 45, tzinfo=UTC),
        outcome="HOME",
        home_elo_pre=1550.0,
        away_elo_pre=1850.0,
    ),
)

STUB_PROBABILITIES: dict[str, tuple[float, float, float]] = {
    HELIX_ID: (0.60, 0.20, 0.20),
    BOURNEMOUTH_ID: (0.28, 0.26, 0.46),
    MARSEILLE_ID: (0.34, 0.36, 0.30),
    RENNES_PSG_ID: (0.22, 0.24, 0.54),
}


def historical_odds_fixture_paths() -> tuple[Path, ...]:
    root = repository_root() / "workers" / "ingestion" / "fixtures" / "the_odds_api"
    return (
        root / "soccer_epl_historical_pilot.json",
        root / "soccer_epl_historical_pilot_later.json",
        root / "soccer_ligue1_historical_pilot.json",
        root / "soccer_ligue1_historical_pilot_later.json",
    )
