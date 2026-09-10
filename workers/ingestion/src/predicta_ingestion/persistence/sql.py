from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import text
from sqlalchemy.engine import Engine

from predicta_ingestion.canonical.models import CanonicalBatch, League, Match, Sport, Team
from predicta_ingestion.clock import Clock
from predicta_ingestion.identity.resolver import IdentityBinding
from predicta_ingestion.ids import stable_entity_id
from predicta_ingestion.persistence.memory import PersistResult
from predicta_ingestion.raw.store import StoredRaw

Executor = Callable[[str, dict[str, Any]], None]


class SqlCanonicalSink:
    """Writes canonical football rows into the shared apps/api PostgreSQL schema."""

    def __init__(
        self,
        *,
        clock: Clock,
        engine: Engine | None = None,
        executor: Executor | None = None,
    ) -> None:
        if engine is None and executor is None:
            raise ValueError("SqlCanonicalSink requires an engine or a test executor.")
        self._clock = clock
        self._engine = engine
        self._executor = executor

    def record_raw(self, stored: StoredRaw) -> None:
        envelope = stored.envelope
        self._execute(
            """
            INSERT INTO raw_payloads (
                id, provider, sport_code, resource_type, provider_request_key,
                checksum_sha256, storage_uri, content_type, byte_size,
                collected_at, data_mode, ingested_at
            ) VALUES (
                :id, :provider, :sport_code, :resource_type, :provider_request_key,
                :checksum_sha256, :storage_uri, :content_type, :byte_size,
                :collected_at, :data_mode, :ingested_at
            )
            ON CONFLICT (provider, checksum_sha256) DO NOTHING
            """,
            {
                "id": stored.id,
                "provider": envelope.provider,
                "sport_code": envelope.sport.value if envelope.sport else None,
                "resource_type": envelope.resource.value,
                "provider_request_key": envelope.request_key[:255],
                "checksum_sha256": envelope.checksum_sha256,
                "storage_uri": stored.storage_uri,
                "content_type": envelope.content_type,
                "byte_size": len(envelope.body),
                "collected_at": envelope.collected_at,
                "data_mode": envelope.data_mode.value,
                "ingested_at": self._clock.now(),
            },
        )

    def persist_identity(self, bindings: object) -> None:
        now = self._clock.now()
        for binding in bindings if isinstance(bindings, list) else []:
            if not isinstance(binding, IdentityBinding):
                continue
            self._execute(
                """
                INSERT INTO provider_entity_maps (
                    provider, entity_type, provider_entity_id, canonical_id,
                    resolution_method, confidence, created_at, updated_at
                ) VALUES (
                    :provider, :entity_type, :provider_entity_id, :canonical_id,
                    :resolution_method, :confidence, :created_at, :updated_at
                )
                ON CONFLICT (provider, entity_type, provider_entity_id) DO UPDATE SET
                    canonical_id = EXCLUDED.canonical_id,
                    resolution_method = EXCLUDED.resolution_method,
                    confidence = EXCLUDED.confidence,
                    updated_at = EXCLUDED.updated_at
                """,
                {
                    "provider": binding.provider,
                    "entity_type": binding.entity_type.value,
                    "provider_entity_id": binding.provider_entity_id,
                    "canonical_id": binding.canonical_id,
                    "resolution_method": binding.method.value,
                    "confidence": binding.confidence,
                    "created_at": now,
                    "updated_at": now,
                },
            )

    def persist(self, batch: CanonicalBatch) -> PersistResult:
        result = PersistResult()
        now = self._clock.now()
        for sport in batch.sports:
            self._upsert_sport(sport, now)
            result.inserted += 1
        for league in batch.leagues:
            self._upsert_league(league, now)
            result.inserted += 1
        for team in batch.teams:
            self._upsert_team(team, now)
            result.inserted += 1
        for match in batch.matches:
            self._upsert_match(match, now)
            result.inserted += 1
        return result

    def record_run(
        self,
        *,
        run_id: str,
        provider: str,
        resource_type: str,
        status: str,
        data_mode: str,
        records_read: int,
        records_accepted: int,
        records_quarantined: int,
        error_summary: str | None = None,
        cursor: str | None = None,
    ) -> None:
        now = self._clock.now()
        self._execute(
            """
            INSERT INTO ingestion_runs (
                id, provider, resource_type, status, started_at, finished_at,
                cursor, records_read, records_accepted, records_quarantined,
                error_summary, data_mode
            ) VALUES (
                :id, :provider, :resource_type, :status, :started_at, :finished_at,
                :cursor, :records_read, :records_accepted, :records_quarantined,
                :error_summary, :data_mode
            )
            """,
            {
                "id": run_id,
                "provider": provider,
                "resource_type": resource_type,
                "status": status,
                "started_at": now,
                "finished_at": now,
                "cursor": cursor,
                "records_read": records_read,
                "records_accepted": records_accepted,
                "records_quarantined": records_quarantined,
                "error_summary": error_summary,
                "data_mode": data_mode,
            },
        )

    def record_quarantine(
        self,
        *,
        reason_code: str,
        detail: str,
        provider: str,
        entity_type: str,
        data_mode: str,
        run_id: str | None = None,
        raw_payload_id: str | None = None,
        provider_entity_id: str | None = None,
    ) -> None:
        self._execute(
            """
            INSERT INTO quarantine_records (
                id, run_id, raw_payload_id, provider, entity_type, provider_entity_id,
                reason_code, detail, created_at, data_mode
            ) VALUES (
                :id, :run_id, :raw_payload_id, :provider, :entity_type, :provider_entity_id,
                :reason_code, :detail, :created_at, :data_mode
            )
            """,
            {
                "id": stable_entity_id("quarantine", provider, reason_code, str(self._clock.now())),
                "run_id": run_id,
                "raw_payload_id": raw_payload_id,
                "provider": provider,
                "entity_type": entity_type,
                "provider_entity_id": provider_entity_id,
                "reason_code": reason_code,
                "detail": detail,
                "created_at": self._clock.now(),
                "data_mode": data_mode,
            },
        )

    def _upsert_sport(self, sport: Sport, now: object) -> None:
        self._execute(
            """
            INSERT INTO sports (id, code, name, created_at)
            VALUES (:id, :code, :name, :created_at)
            ON CONFLICT (id) DO NOTHING
            """,
            {"id": sport.id, "code": sport.code.value, "name": sport.name, "created_at": now},
        )

    def _upsert_league(self, league: League, now: object) -> None:
        self._execute(
            """
            INSERT INTO leagues (id, sport_id, name, country, season, tier, slug, provider_season_id, created_at)
            VALUES (:id, :sport_id, :name, :country, :season, :tier, :slug, :provider_season_id, :created_at)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                country = EXCLUDED.country,
                season = EXCLUDED.season,
                tier = EXCLUDED.tier,
                slug = EXCLUDED.slug,
                provider_season_id = EXCLUDED.provider_season_id
            """,
            {
                "id": league.id,
                "sport_id": league.sport_id,
                "name": league.name,
                "country": league.country,
                "season": league.season,
                "tier": league.tier,
                "slug": league.competition_id,
                "provider_season_id": league.provider_season_id,
                "created_at": now,
            },
        )

    def _upsert_team(self, team: Team, now: object) -> None:
        self._execute(
            """
            INSERT INTO teams (id, sport_id, league_id, name, short_name, abbreviation, created_at)
            VALUES (:id, :sport_id, :league_id, :name, :short_name, :abbreviation, :created_at)
            ON CONFLICT (id) DO UPDATE SET
                name = EXCLUDED.name,
                short_name = EXCLUDED.short_name,
                abbreviation = EXCLUDED.abbreviation
            """,
            {
                "id": team.id,
                "sport_id": team.sport_id,
                "league_id": team.league_id,
                "name": team.name,
                "short_name": team.short_name,
                "abbreviation": team.abbreviation,
                "created_at": now,
            },
        )

    def _upsert_match(self, match: Match, now: object) -> None:
        provenance = match.provenance
        self._execute(
            """
            INSERT INTO matches (
                id, sport_id, league_id, home_team_id, away_team_id, kickoff_at, status,
                venue, home_score, away_score, source, collected_at, available_at,
                data_mode, raw_payload_id, created_at, updated_at
            ) VALUES (
                :id, :sport_id, :league_id, :home_team_id, :away_team_id, :kickoff_at, :status,
                :venue, :home_score, :away_score, :source, :collected_at, :available_at,
                :data_mode, :raw_payload_id, :created_at, :updated_at
            )
            ON CONFLICT (id) DO UPDATE SET
                status = EXCLUDED.status,
                venue = EXCLUDED.venue,
                home_score = EXCLUDED.home_score,
                away_score = EXCLUDED.away_score,
                source = EXCLUDED.source,
                collected_at = EXCLUDED.collected_at,
                available_at = EXCLUDED.available_at,
                data_mode = EXCLUDED.data_mode,
                raw_payload_id = EXCLUDED.raw_payload_id,
                updated_at = EXCLUDED.updated_at
            """,
            {
                "id": match.id,
                "sport_id": match.sport_id,
                "league_id": match.league_id,
                "home_team_id": match.home_team_id,
                "away_team_id": match.away_team_id,
                "kickoff_at": match.kickoff_at,
                "status": match.status.value,
                "venue": match.venue,
                "home_score": match.home_score,
                "away_score": match.away_score,
                "source": provenance.source,
                "collected_at": provenance.collected_at,
                "available_at": provenance.available_at,
                "data_mode": provenance.data_mode.value,
                "raw_payload_id": provenance.raw_payload_id,
                "created_at": now,
                "updated_at": now,
            },
        )

    def _execute(self, sql: str, params: dict[str, Any]) -> None:
        if self._executor is not None:
            self._executor(sql, params)
            return
        assert self._engine is not None
        with self._engine.begin() as connection:
            connection.execute(text(sql), params)
