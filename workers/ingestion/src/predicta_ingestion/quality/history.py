from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from predicta_ingestion.canonical.enums import DataMode, MatchStatus
from predicta_ingestion.canonical.models import Match
from predicta_ingestion.quality.quarantine import QuarantineItem


@dataclass
class SeasonQualityReport:
    competition: str
    season: str
    season_id: str
    fetched_count: int
    normalized_count: int
    inserted_count: int
    duplicate_count: int
    quarantined_count: int
    missing_score_count: int
    missing_team_count: int
    finished_count: int
    future_count: int
    other_status_count: int
    team_count: int
    date_min: datetime | None
    date_max: datetime | None
    provider: str
    data_mode: str
    ingestion_run_id: str
    quarantined_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, object]:
        return {
            "competition": self.competition,
            "season": self.season,
            "season_id": self.season_id,
            "fetched_count": self.fetched_count,
            "normalized_count": self.normalized_count,
            "inserted_count": self.inserted_count,
            "duplicate_count": self.duplicate_count,
            "quarantined_count": self.quarantined_count,
            "missing_score_count": self.missing_score_count,
            "missing_team_count": self.missing_team_count,
            "finished_count": self.finished_count,
            "future_count": self.future_count,
            "other_status_count": self.other_status_count,
            "team_count": self.team_count,
            "date_min": self.date_min.isoformat() if self.date_min else None,
            "date_max": self.date_max.isoformat() if self.date_max else None,
            "provider": self.provider,
            "data_mode": self.data_mode,
            "ingestion_run_id": self.ingestion_run_id,
            "quarantined_reasons": self.quarantined_reasons,
        }


def build_season_quality_report(
    *,
    competition: str,
    season: str,
    season_id: str,
    fetched_count: int,
    matches: list[Match],
    inserted_ids: set[str],
    duplicate_ids: set[str],
    quarantined: list[QuarantineItem],
    provider: str,
    data_mode: DataMode,
    ingestion_run_id: str,
) -> SeasonQualityReport:
    kickoffs = [item.kickoff_at for item in matches]
    missing_scores = sum(1 for item in matches if item.home_score is None or item.away_score is None)
    missing_scores += sum(1 for item in quarantined if "score" in item.reason_code or "score" in item.detail.lower())
    missing_teams = sum(
        1
        for item in quarantined
        if item.reason_code in {"missing_provider_id", "same_team"} or "participant" in item.detail.lower()
    )
    finished = [item for item in matches if item.status is MatchStatus.FINISHED]
    future = [item for item in matches if item.status is MatchStatus.SCHEDULED]
    team_ids = {item.home_team_id for item in matches if item.home_team_id} | {
        item.away_team_id for item in matches if item.away_team_id
    }
    return SeasonQualityReport(
        competition=competition,
        season=season,
        season_id=season_id,
        fetched_count=fetched_count,
        normalized_count=len(matches),
        inserted_count=len(inserted_ids),
        duplicate_count=len(duplicate_ids),
        quarantined_count=len(quarantined),
        missing_score_count=missing_scores,
        missing_team_count=missing_teams,
        finished_count=len(finished),
        future_count=len(future),
        other_status_count=len(matches) - len(finished) - len(future),
        team_count=len(team_ids),
        date_min=min(kickoffs) if kickoffs else None,
        date_max=max(kickoffs) if kickoffs else None,
        provider=provider,
        data_mode=data_mode.value,
        ingestion_run_id=ingestion_run_id,
        quarantined_reasons=[item.reason_code for item in quarantined],
    )


def finished_without_score(match: Match) -> bool:
    return match.status is MatchStatus.FINISHED and (match.home_score is None or match.away_score is None)
