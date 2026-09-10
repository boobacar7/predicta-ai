from __future__ import annotations

from datetime import date

from app.ai_picks.models import MatchCandidate
from app.match_identity.repository import MatchIdentityRepository


class CanonicalMatchCandidateSource:
    """Resolve the configured V0.1 universe through canonical match identity."""

    def __init__(self, identities: MatchIdentityRepository, match_ids: tuple[str, ...]) -> None:
        candidates = []
        for match_id in sorted(set(match_ids)):
            identity = identities.get(match_id)
            if identity is None:
                continue
            candidates.append(MatchCandidate.from_identity(identity))
        self._candidates = tuple(sorted(candidates, key=lambda item: item.match_id))

    def list_candidates(self, *, match_date: date | None, league: str | None) -> list[MatchCandidate]:
        return [
            item
            for item in self._candidates
            if (match_date is None or item.kickoff_at.date() == match_date)
            and (league is None or item.league.casefold() == league.casefold())
        ]
