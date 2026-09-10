from __future__ import annotations

from datetime import date, datetime
from pathlib import Path

from app.ai_picks.models import MatchCandidate
from app.predictions.runtime import ensure_ml_on_path


class ParquetMatchCandidateSource:
    """Resolve the configured V0.1 universe from the real PIT dataset."""

    def __init__(self, dataset_path: Path, match_ids: tuple[str, ...]) -> None:
        ensure_ml_on_path()
        from predicta_ml.features.dataset import load_football_dataset

        dataset = load_football_dataset(dataset_path)
        configured = set(match_ids)
        candidates: list[MatchCandidate] = []
        for _, row in dataset.frame.iterrows():
            match_id = str(row["match_id"])
            if match_id not in configured:
                continue
            value = row["event_at"]
            kickoff = value.to_pydatetime() if hasattr(value, "to_pydatetime") else value
            if not isinstance(kickoff, datetime):
                raise ValueError(f"Invalid event_at for AI Picks candidate '{match_id}'.")
            candidates.append(
                MatchCandidate(
                    match_id=match_id,
                    league=str(row["competition_name"]),
                    kickoff_at=kickoff,
                )
            )
        self._candidates = tuple(sorted(candidates, key=lambda item: item.match_id))

    def list_candidates(self, *, match_date: date | None, league: str | None) -> list[MatchCandidate]:
        return [
            item
            for item in self._candidates
            if (match_date is None or item.kickoff_at.date() == match_date)
            and (league is None or item.league.casefold() == league.casefold())
        ]
