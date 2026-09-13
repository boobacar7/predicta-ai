"""Canonical structural match identity resolution."""

from app.match_identity.models import HistoricalMatchIdentity, MatchIdentity
from app.match_identity.repository import MatchIdentityRepository

__all__ = ["HistoricalMatchIdentity", "MatchIdentity", "MatchIdentityRepository"]
