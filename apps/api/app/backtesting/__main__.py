from __future__ import annotations

import json
import sys

from app.predictions.runtime import ensure_ingestion_on_path, ensure_ml_on_path, repository_root
from app.predictions.types import CANDIDATE_MODEL_VERSION

ensure_ml_on_path()
ensure_ingestion_on_path()

from sqlalchemy import create_engine, text  # noqa: E402

from app.backtesting.fixture_universe import LIVE_WEEKEND_END, LIVE_WEEKEND_START  # noqa: E402
from app.backtesting.persisted import run_persisted_weekend_pilot, weekend_catalog_from_parquet  # noqa: E402
from app.backtesting.pilot import run_fixture_pilot, run_live_weekend_model_pilot  # noqa: E402
from app.core.config import Settings, get_settings  # noqa: E402
from app.odds.sql_repository import SqlOddsRepository  # noqa: E402
from app.odds.the_odds_api import LIVE_ODDS_SOURCE  # noqa: E402
from app.odds.types import OddsSnapshot  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "persisted-weekend":
        json.dump(_persisted_weekend_payload(), sys.stdout, indent=2, sort_keys=True, default=str)
        sys.stdout.write("\n")
        return 0
    report = run_fixture_pilot()
    payload: dict[str, object] = {"fixture": report, "live_weekend": None}
    dataset = repository_root() / "workers" / "ingestion" / "var" / "football-1x2-history.parquet"
    registry = repository_root() / "workers" / "ml" / "var" / "registry"
    if dataset.is_file() and (registry / CANDIDATE_MODEL_VERSION / "artefact.joblib").is_file():
        payload["live_weekend"] = run_live_weekend_model_pilot(dataset_path=dataset, registry_dir=registry)
    json.dump(payload, sys.stdout, indent=2, sort_keys=True, default=str)
    sys.stdout.write("\n")
    return 0


def _persisted_weekend_payload() -> dict[str, object]:
    dataset = repository_root() / "workers" / "ingestion" / "var" / "football-1x2-history.parquet"
    registry = repository_root() / "workers" / "ml" / "var" / "registry"
    settings = get_settings()
    catalog = weekend_catalog_from_parquet(dataset, names=_weekend_team_names(settings))
    repository = SqlOddsRepository(settings)
    snapshots: list[OddsSnapshot] = []
    for match in catalog:
        snapshots.extend(
            repository.history(
                match.match_id,
                "1X2",
                source=LIVE_ODDS_SOURCE,
                data_mode="live",
            )
        )
    return run_persisted_weekend_pilot(
        catalog=catalog,
        snapshots=tuple(snapshots),
        dataset_path=dataset,
        registry_dir=registry,
        persist_meta={"odds_source": "postgresql:odds_snapshots", "loaded_snapshots": len(snapshots)},
    )


def _weekend_team_names(settings: Settings) -> dict[str, tuple[str, str]]:
    names: dict[str, tuple[str, str]] = {}
    engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
    query = text(
        """
        SELECT m.id, ht.name AS home_name, at.name AS away_name
        FROM matches m
        JOIN teams ht ON ht.id = m.home_team_id
        JOIN teams at ON at.id = m.away_team_id
        WHERE m.kickoff_at >= :window_start AND m.kickoff_at < :window_end
        """
    )
    with engine.connect() as connection:
        for row in connection.execute(query, {"window_start": LIVE_WEEKEND_START, "window_end": LIVE_WEEKEND_END}):
            names[str(row.id)] = (str(row.home_name), str(row.away_name))
    return names


if __name__ == "__main__":
    raise SystemExit(main())
