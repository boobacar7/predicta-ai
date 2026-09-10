from __future__ import annotations

from app.core.errors import NotFoundError
from app.match_identity.models import HistoricalMatchIdentity
from app.match_identity.repository import MatchIdentityRepository
from app.schemas import MatchDetail
from app.services.catalog import MatchService


class MatchResolutionService:
    """Resolve UI matches first, then canonical historical structural identity."""

    def __init__(self, matches: MatchService, identities: MatchIdentityRepository) -> None:
        self._matches = matches
        self._identities = identities

    def get(self, match_id: str) -> MatchDetail | HistoricalMatchIdentity:
        try:
            return self._matches.get_match(match_id)
        except NotFoundError:
            identity = self._identities.get(match_id)
            if identity is None:
                raise NotFoundError("Match not found.", instance=f"/matches/{match_id}") from None
            return HistoricalMatchIdentity.from_identity(identity)
