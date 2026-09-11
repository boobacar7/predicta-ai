from __future__ import annotations

import json
import sys

from app.predictions.runtime import ensure_ingestion_on_path, ensure_ml_on_path, repository_root
from app.predictions.types import CANDIDATE_MODEL_VERSION

ensure_ml_on_path()
ensure_ingestion_on_path()

from sqlalchemy import create_engine, text  # noqa: E402

from app.backtesting.expanded import expanded_catalog_from_parquet, run_persisted_expanded_pilot  # noqa: E402
from app.backtesting.final_test_history import (  # noqa: E402
    final_test_catalog_from_parquet,
    run_persisted_final_test_history,
)
from app.backtesting.fixture_universe import LIVE_WEEKEND_END, LIVE_WEEKEND_START  # noqa: E402
from app.backtesting.persisted import run_persisted_weekend_pilot, weekend_catalog_from_parquet  # noqa: E402
from app.backtesting.pilot import run_fixture_pilot, run_live_weekend_model_pilot  # noqa: E402
from app.core.config import Settings, get_settings  # noqa: E402
from app.odds.sql_repository import SqlOddsRepository  # noqa: E402
from app.odds.the_odds_api import LIVE_ODDS_SOURCE  # noqa: E402
from app.odds.types import OddsSnapshot  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if args and args[0] == "production-oos":
        json.dump(_production_oos_payload(), sys.stdout, indent=2, sort_keys=True, default=str)
        sys.stdout.write("\n")
        return 0
    if args and args[0] == "persisted-weekend":
        json.dump(_persisted_weekend_payload(), sys.stdout, indent=2, sort_keys=True, default=str)
        sys.stdout.write("\n")
        return 0
    if args and args[0] == "persisted-expanded":
        json.dump(_persisted_expanded_payload(), sys.stdout, indent=2, sort_keys=True, default=str)
        sys.stdout.write("\n")
        return 0
    if args and args[0] == "persisted-final-test-history":
        json.dump(_persisted_final_test_payload(), sys.stdout, indent=2, sort_keys=True, default=str)
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


def _production_oos_payload() -> dict[str, object]:
    from predicta_ml.constants import default_committed_reports_dir
    from predicta_ml.oos.runner import run_from_paths, write_reports

    from app.backtesting.production_oos import optional_persisted_oos_quotes, production_calculator

    dataset = repository_root() / "workers" / "ingestion" / "var" / "football-1x2-history.parquet"
    quotes = optional_persisted_oos_quotes()
    run = run_from_paths(dataset, quotes=quotes, calculator=production_calculator())
    paths = write_reports(run, output_dir=default_committed_reports_dir())
    payload = dict(run.report)
    payload["paths"] = paths
    payload["odds_source"] = "persisted_analytical_dataset" if quotes else "none"
    payload["new_api_credits"] = 0
    return payload


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


def _persisted_expanded_payload() -> dict[str, object]:
    dataset = repository_root() / "workers" / "ingestion" / "var" / "football-1x2-history.parquet"
    registry = repository_root() / "workers" / "ml" / "var" / "registry"
    settings = get_settings()
    catalog = expanded_catalog_from_parquet(dataset, names=_expanded_team_names(settings))
    repository = SqlOddsRepository(settings)
    snapshots = repository.history_many(
        [item.match_id for item in catalog],
        "1X2",
        source=LIVE_ODDS_SOURCE,
        data_mode="live",
    )
    return run_persisted_expanded_pilot(
        catalog=catalog,
        snapshots=snapshots,
        dataset_path=dataset,
        registry_dir=registry,
        persist_meta={"odds_source": "postgresql:odds_snapshots", "loaded_snapshots": len(snapshots)},
    )


def _persisted_final_test_payload() -> dict[str, object]:
    dataset = repository_root() / "workers" / "ingestion" / "var" / "football-1x2-history.parquet"
    registry = repository_root() / "workers" / "ml" / "var" / "registry"
    settings = get_settings()
    catalog = final_test_catalog_from_parquet(dataset, names=_expanded_team_names(settings))
    repository = SqlOddsRepository(settings)
    snapshots = repository.history_many(
        [item.match_id for item in catalog],
        "1X2",
        source=LIVE_ODDS_SOURCE,
        data_mode="live",
    )
    return run_persisted_final_test_history(
        catalog=catalog,
        snapshots=snapshots,
        dataset_path=dataset,
        registry_dir=registry,
        persist_meta={"odds_source": "postgresql:odds_snapshots", "loaded_snapshots": len(snapshots)},
    )


def _expanded_team_names(settings: Settings) -> dict[str, tuple[str, str]]:
    names: dict[str, tuple[str, str]] = {}
    engine = create_engine(settings.database_url, pool_pre_ping=True, future=True)
    query = text(
        """
        SELECT m.id, ht.name AS home_name, at.name AS away_name
        FROM matches m
        JOIN teams ht ON ht.id = m.home_team_id
        JOIN teams at ON at.id = m.away_team_id
        JOIN leagues l ON l.id = m.league_id
        WHERE l.slug IN ('premier-league', 'ligue-1')
           OR lower(l.name) IN ('premier league', 'ligue 1')
        """
    )
    with engine.connect() as connection:
        for row in connection.execute(query):
            names[str(row.id)] = (str(row.home_name), str(row.away_name))
    return names


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
