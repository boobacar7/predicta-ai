from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Protocol

from sqlalchemy import text

from app.core.config import Settings
from app.db.session import get_session_factory
from app.match_identity.models import MatchIdentity
from app.predictions.runtime import ensure_ml_on_path


class MatchIdentityRepository(Protocol):
    def get(self, match_id: str) -> MatchIdentity | None: ...


class NullMatchIdentityRepository:
    """Used when the historical archive is not mounted. Never invents identity."""

    def get(self, match_id: str) -> MatchIdentity | None:
        return None


class ParquetArchiveMatchIdentityRepository:
    """Project canonical IDs from PIT parquet and structural labels from its raw provenance."""

    def __init__(self, dataset_path: Path, raw_archive_dir: Path) -> None:
        ensure_ml_on_path()
        from predicta_ml.features.dataset import load_football_dataset

        dataset = load_football_dataset(dataset_path)
        self._rows = {
            str(row["match_id"]): {
                "match_id": str(row["match_id"]),
                "home_team_id": str(row["home_team_id"]),
                "away_team_id": str(row["away_team_id"]),
                "league": str(row["competition_name"]),
                "kickoff_at": self._datetime(row["event_at"]),
                "raw_payload_id": str(row["raw_payload_id"]),
                "data_mode": str(row["data_mode"]),
            }
            for _, row in dataset.frame.iterrows()
        }
        self._raw_paths = {path.stem: path for path in raw_archive_dir.rglob("*.json")}
        self._cache: dict[str, MatchIdentity] = {}

    def get(self, match_id: str) -> MatchIdentity | None:
        cached = self._cache.get(match_id)
        if cached is not None:
            return cached
        row = self._rows.get(match_id)
        if row is None:
            return None
        home_name, away_name = self._structural_names(row)
        identity = MatchIdentity(
            match_id=match_id,
            home_team_id=str(row["home_team_id"]),
            away_team_id=str(row["away_team_id"]),
            home_team=home_name,
            away_team=away_name,
            league=str(row["league"]),
            kickoff_at=self._datetime(row["kickoff_at"]),
            data_mode="live" if row["data_mode"] == "live" else "mock",
        )
        self._cache[match_id] = identity
        return identity

    def _structural_names(self, row: dict[str, object]) -> tuple[str | None, str | None]:
        path = self._raw_paths.get(str(row["raw_payload_id"]))
        if path is None:
            return None, None
        envelope = json.loads(path.read_text(encoding="utf-8"))
        body = json.loads(str(envelope.get("body_utf8") or "{}"))
        fixtures = body.get("data")
        if not isinstance(fixtures, list):
            return None, None
        for raw in fixtures:
            if not isinstance(raw, dict) or self._canonical_match_id(raw.get("id")) != row["match_id"]:
                continue
            if self._fixture_kickoff(raw) != self._datetime(row["kickoff_at"]):
                return None, None
            participants = raw.get("participants")
            if not isinstance(participants, list):
                return None, None
            home = self._participant(participants, "home", str(row["home_team_id"]))
            away = self._participant(participants, "away", str(row["away_team_id"]))
            return home, away
        return None, None

    @staticmethod
    def _participant(items: list[Any], location: str, canonical_team_id: str) -> str | None:
        for item in items:
            if not isinstance(item, dict):
                continue
            meta = item.get("meta")
            if not isinstance(meta, dict) or meta.get("location") != location:
                continue
            if f"tm_football-sportmonks-{item.get('id')}" != canonical_team_id:
                return None
            name = str(item.get("name") or "").strip()
            return name or None
        return None

    @staticmethod
    def _fixture_kickoff(raw: dict[str, Any]) -> datetime | None:
        value = raw.get("starting_at")
        if not isinstance(value, str):
            return None
        parsed = datetime.fromisoformat(value.replace(" ", "T") + "+00:00")
        return parsed

    @staticmethod
    def _canonical_match_id(provider_id: object) -> str:
        return f"mth_football-sportmonks-{provider_id}"

    @staticmethod
    def _datetime(value: object) -> datetime:
        if isinstance(value, datetime):
            return value
        if hasattr(value, "to_pydatetime"):
            converted = value.to_pydatetime()
            if isinstance(converted, datetime):
                return converted
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


class SqlMatchIdentityRepository:
    """Resolve identity from canonical matches, teams, and leagues only."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def get(self, match_id: str) -> MatchIdentity | None:
        statement = text(
            """
            SELECT m.id, m.home_team_id, m.away_team_id, m.kickoff_at, m.data_mode,
                   home.name AS home_team, away.name AS away_team, league.name AS league
            FROM matches AS m
            JOIN teams AS home ON home.id = m.home_team_id
            JOIN teams AS away ON away.id = m.away_team_id
            JOIN leagues AS league ON league.id = m.league_id
            WHERE m.id = :match_id
            """
        )
        with get_session_factory(self._settings)() as session:
            row = session.execute(statement, {"match_id": match_id}).mappings().one_or_none()
        if row is None:
            return None
        return MatchIdentity(
            match_id=str(row["id"]),
            home_team_id=str(row["home_team_id"]),
            away_team_id=str(row["away_team_id"]),
            home_team=str(row["home_team"]) if row["home_team"] else None,
            away_team=str(row["away_team"]) if row["away_team"] else None,
            league=str(row["league"]),
            kickoff_at=ParquetArchiveMatchIdentityRepository._datetime(row["kickoff_at"]),
            data_mode="mock" if row["data_mode"] == "mock" else "live",
        )
