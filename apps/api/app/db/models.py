from datetime import datetime
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class RawPayload(Base):
    """Metadata only. The provider body lives in the immutable object/filesystem store."""

    __tablename__ = "raw_payloads"
    __table_args__ = (UniqueConstraint("provider", "checksum_sha256", name="uq_raw_payload_checksum"),)

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    provider: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    sport_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_request_key: Mapped[str] = mapped_column(String(255), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_uri: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str] = mapped_column(String(128), nullable=False)
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    data_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class IngestionRun(Base):
    __tablename__ = "ingestion_runs"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cursor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    checkpoint: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    records_read: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_accepted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_quarantined: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_mode: Mapped[str] = mapped_column(String(16), nullable=False)


class QuarantineRecord(Base):
    __tablename__ = "quarantine_records"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    run_id: Mapped[str | None] = mapped_column(ForeignKey("ingestion_runs.id"), nullable=True, index=True)
    raw_payload_id: Mapped[str | None] = mapped_column(ForeignKey("raw_payloads.id"), nullable=True)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_entity_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reason_code: Mapped[str] = mapped_column(String(64), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)
    payload_excerpt: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    data_mode: Mapped[str] = mapped_column(String(16), nullable=False)


class Sport(Base):
    __tablename__ = "sports"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    leagues: Mapped[list["League"]] = relationship(back_populates="sport")


class League(Base):
    __tablename__ = "leagues"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    sport_id: Mapped[str] = mapped_column(ForeignKey("sports.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(128), nullable=False)
    season: Mapped[str] = mapped_column(String(32), nullable=False)
    tier: Mapped[int] = mapped_column(Integer, nullable=False)
    slug: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    provider_season_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    sport: Mapped[Sport] = relationship(back_populates="leagues")
    teams: Mapped[list["Team"]] = relationship(back_populates="league")


class Team(Base):
    __tablename__ = "teams"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    sport_id: Mapped[str] = mapped_column(ForeignKey("sports.id"), nullable=False, index=True)
    league_id: Mapped[str] = mapped_column(ForeignKey("leagues.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    short_name: Mapped[str] = mapped_column(String(128), nullable=False)
    abbreviation: Mapped[str] = mapped_column(String(12), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    league: Mapped[League] = relationship(back_populates="teams")


class Player(Base):
    __tablename__ = "players"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    sport_id: Mapped[str] = mapped_column(ForeignKey("sports.id"), nullable=False, index=True)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    position: Mapped[str | None] = mapped_column(String(128), nullable=True)
    country: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ProviderEntityMap(Base):
    __tablename__ = "provider_entity_maps"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "entity_type",
            "provider_entity_id",
            name="uq_provider_entity",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_entity_id: Mapped[str] = mapped_column(String(255), nullable=False)
    canonical_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    sport_id: Mapped[str | None] = mapped_column(ForeignKey("sports.id"), nullable=True)
    resolution_method: Mapped[str] = mapped_column(String(32), nullable=False, default="exact_id")
    confidence: Mapped[float | None] = mapped_column(Numeric(8, 6), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    sport_id: Mapped[str] = mapped_column(ForeignKey("sports.id"), nullable=False, index=True)
    league_id: Mapped[str] = mapped_column(ForeignKey("leagues.id"), nullable=False, index=True)
    home_team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), nullable=False)
    away_team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), nullable=False)
    kickoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    venue: Mapped[str | None] = mapped_column(String(255), nullable=True)
    home_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    away_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    data_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    raw_payload_id: Mapped[str | None] = mapped_column(ForeignKey("raw_payloads.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    events: Mapped[list["MatchEvent"]] = relationship(back_populates="match")
    statistics: Mapped[list["MatchStatistic"]] = relationship(back_populates="match")


class MatchEvent(Base):
    __tablename__ = "match_events"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"), nullable=False, index=True)
    minute: Mapped[int | None] = mapped_column(Integer, nullable=True)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id"), nullable=True)
    player_id: Mapped[str | None] = mapped_column(ForeignKey("players.id"), nullable=True)
    event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    freshness: Mapped[str | None] = mapped_column(String(32), nullable=True)
    data_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    raw_payload_id: Mapped[str | None] = mapped_column(ForeignKey("raw_payloads.id"), nullable=True)

    match: Mapped[Match] = relationship(back_populates="events")


class MatchStatistic(Base):
    __tablename__ = "match_statistics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"), nullable=False, index=True)
    stat_key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    home_value: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    away_value: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    availability: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(128), nullable=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    freshness: Mapped[str | None] = mapped_column(String(32), nullable=True)
    data_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    raw_payload_id: Mapped[str | None] = mapped_column(ForeignKey("raw_payloads.id"), nullable=True)

    match: Mapped[Match] = relationship(back_populates="statistics")


class TeamStatistic(Base):
    __tablename__ = "team_statistics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), nullable=False, index=True)
    season: Mapped[str] = mapped_column(String(32), nullable=False)
    stat_key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    availability: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(128), nullable=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    freshness: Mapped[str | None] = mapped_column(String(32), nullable=True)
    data_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    raw_payload_id: Mapped[str | None] = mapped_column(ForeignKey("raw_payloads.id"), nullable=True)


class PlayerStatistic(Base):
    __tablename__ = "player_statistics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    player_id: Mapped[str] = mapped_column(ForeignKey("players.id"), nullable=False, index=True)
    season: Mapped[str] = mapped_column(String(32), nullable=False)
    stat_key: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    value: Mapped[float | None] = mapped_column(Numeric(18, 8), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    availability: Mapped[str] = mapped_column(String(32), nullable=False)
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    provider: Mapped[str | None] = mapped_column(String(128), nullable=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    freshness: Mapped[str | None] = mapped_column(String(32), nullable=True)
    data_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    raw_payload_id: Mapped[str | None] = mapped_column(ForeignKey("raw_payloads.id"), nullable=True)


class OddsSnapshot(Base):
    __tablename__ = "odds_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "bookmaker",
            "match_id",
            "market",
            "observed_at",
            name="uq_odds_snapshot_natural",
        ),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"), nullable=False, index=True)
    market: Mapped[str] = mapped_column(String(64), nullable=False)
    bookmaker: Mapped[str] = mapped_column(String(128), nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    available_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source: Mapped[str | None] = mapped_column(String(128), nullable=True)
    freshness: Mapped[str | None] = mapped_column(String(32), nullable=True)
    data_mode: Mapped[str | None] = mapped_column(String(16), nullable=True)
    raw_payload_id: Mapped[str | None] = mapped_column(ForeignKey("raw_payloads.id"), nullable=True)
    overround: Mapped[float | None] = mapped_column(Numeric(18, 10), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    selections: Mapped[list["OddsSelection"]] = relationship(back_populates="snapshot")


class OddsSelection(Base):
    __tablename__ = "odds_selections"
    __table_args__ = (CheckConstraint("decimal_odds IS NULL OR decimal_odds > 1", name="ck_odds_gt_one"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    snapshot_id: Mapped[str] = mapped_column(ForeignKey("odds_snapshots.id"), nullable=False, index=True)
    selection: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    decimal_odds: Mapped[float | None] = mapped_column(Numeric(18, 10), nullable=True)
    implied_probability_raw: Mapped[float | None] = mapped_column(Numeric(18, 10), nullable=True)
    no_vig_probability: Mapped[float | None] = mapped_column(Numeric(18, 10), nullable=True)

    snapshot: Mapped[OddsSnapshot] = relationship(back_populates="selections")


class Standing(Base):
    __tablename__ = "standings"
    __table_args__ = (
        UniqueConstraint(
            "league_id",
            "season",
            "team_id",
            "as_of",
            "provider",
            name="uq_standing_snapshot",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    league_id: Mapped[str] = mapped_column(ForeignKey("leagues.id"), nullable=False, index=True)
    season: Mapped[str] = mapped_column(String(32), nullable=False)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), nullable=False, index=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    played: Mapped[int | None] = mapped_column(Integer, nullable=True)
    won: Mapped[int | None] = mapped_column(Integer, nullable=True)
    drawn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lost: Mapped[int | None] = mapped_column(Integer, nullable=True)
    goals_for: Mapped[int | None] = mapped_column(Integer, nullable=True)
    goals_against: Mapped[int | None] = mapped_column(Integer, nullable=True)
    availability: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    as_of: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    freshness: Mapped[str | None] = mapped_column(String(32), nullable=True)
    data_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    raw_payload_id: Mapped[str | None] = mapped_column(ForeignKey("raw_payloads.id"), nullable=True)


class Injury(Base):
    __tablename__ = "injuries"
    __table_args__ = (
        UniqueConstraint("provider", "provider_injury_id", name="uq_injury_provider"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    provider_injury_id: Mapped[str] = mapped_column(String(255), nullable=False)
    sport_id: Mapped[str] = mapped_column(ForeignKey("sports.id"), nullable=False)
    player_id: Mapped[str | None] = mapped_column(ForeignKey("players.id"), nullable=True, index=True)
    team_id: Mapped[str | None] = mapped_column(ForeignKey("teams.id"), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    availability: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    freshness: Mapped[str | None] = mapped_column(String(32), nullable=True)
    data_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    raw_payload_id: Mapped[str | None] = mapped_column(ForeignKey("raw_payloads.id"), nullable=True)


class Lineup(Base):
    __tablename__ = "lineups"
    __table_args__ = (
        UniqueConstraint("match_id", "team_id", "observed_at", "provider", name="uq_lineup_snapshot"),
    )

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"), nullable=False, index=True)
    team_id: Mapped[str] = mapped_column(ForeignKey("teams.id"), nullable=False)
    formation: Mapped[str | None] = mapped_column(String(32), nullable=True)
    availability: Mapped[str] = mapped_column(String(32), nullable=False)
    provider: Mapped[str] = mapped_column(String(128), nullable=False)
    source: Mapped[str] = mapped_column(String(128), nullable=False)
    available_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    freshness: Mapped[str | None] = mapped_column(String(32), nullable=True)
    data_mode: Mapped[str] = mapped_column(String(16), nullable=False)
    raw_payload_id: Mapped[str | None] = mapped_column(ForeignKey("raw_payloads.id"), nullable=True)

    players: Mapped[list["LineupPlayer"]] = relationship(back_populates="lineup")


class LineupPlayer(Base):
    __tablename__ = "lineup_players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    lineup_id: Mapped[str] = mapped_column(ForeignKey("lineups.id"), nullable=False, index=True)
    player_id: Mapped[str | None] = mapped_column(ForeignKey("players.id"), nullable=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    jersey_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position: Mapped[str | None] = mapped_column(String(64), nullable=True)

    lineup: Mapped[Lineup] = relationship(back_populates="players")


class ModelVersion(Base):
    __tablename__ = "model_versions"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    family: Mapped[str] = mapped_column(String(64), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    calibrator_version: Mapped[str] = mapped_column(String(64), nullable=False)
    feature_set_version: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    metrics: Mapped[list["ModelMetric"]] = relationship(back_populates="model_version")


class ModelMetric(Base):
    __tablename__ = "model_metrics"
    __table_args__ = (
        CheckConstraint(
            "theoretical_max_drawdown IS NULL OR (theoretical_max_drawdown >= -1 AND theoretical_max_drawdown <= 0)",
            name="ck_drawdown_non_positive",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_version_id: Mapped[str] = mapped_column(ForeignKey("model_versions.id"), nullable=False, index=True)
    sport: Mapped[str] = mapped_column(String(32), nullable=False)
    window_label: Mapped[str] = mapped_column(String(128), nullable=False)
    accuracy: Mapped[float | None] = mapped_column(Numeric(18, 10), nullable=True)
    log_loss: Mapped[float | None] = mapped_column(Numeric(18, 10), nullable=True)
    brier_score: Mapped[float | None] = mapped_column(Numeric(18, 10), nullable=True)
    ece: Mapped[float | None] = mapped_column(Numeric(18, 10), nullable=True)
    theoretical_roi: Mapped[float | None] = mapped_column(Numeric(18, 10), nullable=True)
    theoretical_max_drawdown: Mapped[float | None] = mapped_column(Numeric(18, 10), nullable=True)
    prediction_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    model_version: Mapped[ModelVersion] = relationship(back_populates="metrics")


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"), nullable=False, index=True)
    model_version_id: Mapped[str] = mapped_column(ForeignKey("model_versions.id"), nullable=False, index=True)
    market: Mapped[str] = mapped_column(String(64), nullable=False)
    cutoff_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    outcomes: Mapped[list["PredictionOutcome"]] = relationship(back_populates="prediction")
    factors: Mapped[list["PredictionFactor"]] = relationship(back_populates="prediction")


class PredictionOutcome(Base):
    __tablename__ = "prediction_outcomes"
    __table_args__ = (
        CheckConstraint(
            "model_probability IS NULL OR (model_probability >= 0 AND model_probability <= 1)",
            name="ck_model_probability",
        ),
        CheckConstraint(
            "calibrated_probability IS NULL OR (calibrated_probability >= 0 AND calibrated_probability <= 1)",
            name="ck_calibrated_probability",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    prediction_id: Mapped[str] = mapped_column(ForeignKey("predictions.id"), nullable=False, index=True)
    selection: Mapped[str] = mapped_column(String(64), nullable=False)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    model_probability: Mapped[float | None] = mapped_column(Numeric(18, 10), nullable=True)
    calibrated_probability: Mapped[float | None] = mapped_column(Numeric(18, 10), nullable=True)

    prediction: Mapped[Prediction] = relationship(back_populates="outcomes")


class PredictionFactor(Base):
    __tablename__ = "prediction_factors"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    prediction_id: Mapped[str] = mapped_column(ForeignKey("predictions.id"), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(128), nullable=False)
    direction: Mapped[str] = mapped_column(String(16), nullable=False)
    weight: Mapped[str] = mapped_column(String(16), nullable=False)
    detail: Mapped[str] = mapped_column(Text, nullable=False)

    prediction: Mapped[Prediction] = relationship(back_populates="factors")


class PublishedPick(Base):
    __tablename__ = "published_picks"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"), nullable=False, index=True)
    prediction_id: Mapped[str | None] = mapped_column(ForeignKey("predictions.id"), nullable=True)
    market: Mapped[str] = mapped_column(String(64), nullable=False)
    selection: Mapped[str] = mapped_column(String(64), nullable=False)
    selection_label: Mapped[str] = mapped_column(String(128), nullable=False)
    calibrated_probability: Mapped[float | None] = mapped_column(Numeric(18, 10), nullable=True)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)
    criteria: Mapped[str] = mapped_column(Text, nullable=False)
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AiAnalysis(Base):
    __tablename__ = "ai_analyses"

    id: Mapped[str] = mapped_column(String(128), primary_key=True)
    match_id: Mapped[str] = mapped_column(ForeignKey("matches.id"), nullable=False, index=True)
    fact_pack: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    messages: Mapped[list[Any]] = mapped_column(JSONB, nullable=False)
    llm_model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
