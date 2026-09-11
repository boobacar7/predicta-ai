from enum import StrEnum


class SportCode(StrEnum):
    FOOTBALL = "football"
    BASKETBALL = "basketball"
    TENNIS = "tennis"


class MatchStatus(StrEnum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"
    POSTPONED = "postponed"
    CANCELLED = "cancelled"


class Availability(StrEnum):
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    PARTIAL = "partial"
    STALE = "stale"


class Freshness(StrEnum):
    FRESH = "fresh"
    ACCEPTABLE = "acceptable"
    STALE = "stale"


class DataMode(StrEnum):
    MOCK = "mock"
    LIVE = "live"


class ResourceType(StrEnum):
    LEAGUES = "leagues"
    SEASONS = "seasons"
    FIXTURES = "fixtures"
    STANDINGS = "standings"
    MATCH_EVENTS = "match_events"
    TEAM_STATS = "team_stats"
    PLAYER_STATS = "player_stats"
    INJURIES = "injuries"
    LINEUPS = "lineups"
    ODDS = "odds"


class EntityType(StrEnum):
    SPORT = "sport"
    LEAGUE = "league"
    TEAM = "team"
    PLAYER = "player"
    MATCH = "match"
    INJURY = "injury"
    LINEUP = "lineup"
    ODDS_SNAPSHOT = "odds_snapshot"


class LineupRole(StrEnum):
    STARTER = "starter"
    BENCH = "bench"
    UNKNOWN = "unknown"


class InjuryStatus(StrEnum):
    INJURED = "injured"
    DOUBTFUL = "doubtful"
    SUSPENDED = "suspended"
    RETURNED = "returned"
    UNKNOWN = "unknown"


class ResolutionMethod(StrEnum):
    EXACT_ID = "exact_id"
    HISTORICAL_ALIAS = "historical_alias"
    EXPLICIT_ALIAS = "explicit_alias"
    NORMALIZED_NAME = "normalized_name"
    MANUAL = "manual"
