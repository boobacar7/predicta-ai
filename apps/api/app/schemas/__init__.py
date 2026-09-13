from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from app.core.clock import to_rfc3339

SportCode = Literal["football", "basketball", "tennis"]
DataMode = Literal["mock", "live"]
AvailabilityStatus = Literal["available", "unavailable", "partial", "stale"]
FreshnessLevel = Literal["fresh", "acceptable", "stale"]
ConfidenceLevel = Literal["low", "medium", "high"]
MatchStatus = Literal["scheduled", "live", "finished", "postponed"]
FormResult = Literal["W", "D", "L"]
InsightKind = Literal["model", "data", "value", "caution"]
FactorDirection = Literal["home", "away", "neutral"]
FactorWeight = Literal["low", "medium", "high"]
AnalystRole = Literal["user", "analyst"]
FootballModelStatus = Literal["candidate", "champion"]


class ApiModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DataQuality(ApiModel):
    availability: AvailabilityStatus
    source: str | None
    observed_at: datetime | None
    freshness: FreshnessLevel | None
    note: str | None

    @field_serializer("observed_at")
    def _observed_at(self, value: datetime | None) -> str | None:
        return to_rfc3339(value) if value else None


class EnvelopeMetadata(ApiModel):
    data_mode: DataMode
    generated_at: datetime
    request_id: str

    @field_serializer("generated_at")
    def _generated_at(self, value: datetime) -> str:
        return to_rfc3339(value)


class IdentifiedEntity(ApiModel):
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1)


class Sport(ApiModel):
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1)
    code: SportCode


class League(ApiModel):
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1)
    sport: SportCode
    country: str
    season: str
    tier: int = Field(ge=1)


class Team(ApiModel):
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1)
    short_name: str = Field(min_length=1)
    sport: SportCode
    league_id: str = Field(min_length=1, max_length=128)
    abbreviation: str = Field(min_length=1, max_length=12)


class Player(ApiModel):
    id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1)
    sport: SportCode
    team_id: str | None
    position: str | None
    country: str


class UnavailableField(ApiModel):
    field: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class NamedStat(ApiModel):
    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    value: float | None
    unit: str | None
    quality: DataQuality


class Scoreline(ApiModel):
    home: int | None = Field(default=None, ge=0)
    away: int | None = Field(default=None, ge=0)
    quality: DataQuality


class MatchEvent(ApiModel):
    id: str = Field(min_length=1, max_length=128)
    minute: int | None = Field(default=None, ge=0)
    type: str = Field(min_length=1)
    label: str = Field(min_length=1)
    team_id: str | None
    quality: DataQuality


class MatchStatistic(ApiModel):
    key: str = Field(min_length=1)
    label: str = Field(min_length=1)
    home_value: float | None
    away_value: float | None
    unit: str | None
    quality: DataQuality


class TeamFormSide(ApiModel):
    team_id: str = Field(min_length=1, max_length=128)
    results: list[FormResult | None]
    quality: DataQuality


class ProbabilityOutcome(ApiModel):
    selection: str = Field(min_length=1)
    label: str = Field(min_length=1)
    model_probability: float | None = Field(default=None, ge=0, le=1)
    calibrated_probability: float | None = Field(default=None, ge=0, le=1)
    quality: DataQuality


class PredictionPreview(ApiModel):
    model_version: str = Field(min_length=1)
    market: str = Field(min_length=1)
    confidence: ConfidenceLevel
    leading_selection: str = Field(min_length=1)
    leading_probability: float | None = Field(default=None, ge=0, le=1)
    cutoff_at: datetime
    outcomes: list[ProbabilityOutcome]
    quality: DataQuality

    @field_serializer("cutoff_at")
    def _cutoff(self, value: datetime) -> str:
        return to_rfc3339(value)


class PredictionFactor(ApiModel):
    id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1)
    direction: FactorDirection
    weight: FactorWeight
    detail: str
    quality: DataQuality


class PredictionDetail(ApiModel):
    id: str = Field(min_length=1, max_length=128)
    match_id: str = Field(min_length=1, max_length=128)
    market: str = Field(min_length=1)
    model_family: str = Field(min_length=1)
    model_version: str = Field(min_length=1)
    calibrator_version: str = Field(min_length=1)
    feature_set_version: str = Field(min_length=1)
    cutoff_at: datetime
    confidence: ConfidenceLevel
    outcomes: list[ProbabilityOutcome] = Field(min_length=2)
    factors: list[PredictionFactor]
    quality: DataQuality

    @field_serializer("cutoff_at")
    def _cutoff(self, value: datetime) -> str:
        return to_rfc3339(value)


class OddsSelection(ApiModel):
    selection: str = Field(min_length=1)
    label: str = Field(min_length=1)
    decimal_odds: float | None = Field(default=None, gt=1)
    implied_probability_raw: float | None = Field(default=None, ge=0, le=1)
    no_vig_probability: float | None = Field(default=None, ge=0, le=1)
    quality: DataQuality


class OddsSnapshot(ApiModel):
    id: str = Field(min_length=1, max_length=128)
    match_id: str = Field(min_length=1, max_length=128)
    market: str = Field(min_length=1)
    bookmaker: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    observed_at: datetime
    overround: float | None = Field(default=None, ge=0)
    selections: list[OddsSelection] = Field(min_length=2)
    quality: DataQuality

    @field_serializer("observed_at")
    def _observed(self, value: datetime) -> str:
        return to_rfc3339(value)


class ValuePreview(ApiModel):
    selection: str = Field(min_length=1)
    edge: float | None = Field(default=None, ge=-1, le=1)
    expected_value: float | None = Field(default=None, ge=-1)
    formula_version: str = Field(min_length=1)
    quality: DataQuality


class MatchSummary(ApiModel):
    id: str = Field(min_length=1, max_length=128)
    sport: SportCode
    league: League
    home: Team
    away: Team
    kickoff_at: datetime
    status: MatchStatus
    venue: str | None
    score: Scoreline
    prediction_preview: PredictionPreview | None
    value_preview: ValuePreview | None
    quality: DataQuality

    @field_serializer("kickoff_at")
    def _kickoff(self, value: datetime) -> str:
        return to_rfc3339(value)


class MatchDetail(MatchSummary):
    timeline: list[MatchEvent]
    stats: list[MatchStatistic]
    odds: OddsSnapshot | None
    prediction: PredictionDetail | None
    form: list[TeamFormSide]
    unavailable_fields: list[UnavailableField]


class ValueOpportunity(ApiModel):
    id: str = Field(min_length=1, max_length=128)
    match: MatchSummary
    market: str = Field(min_length=1)
    selection: str = Field(min_length=1)
    selection_label: str = Field(min_length=1)
    calibrated_probability: float | None = Field(default=None, ge=0, le=1)
    decimal_odds: float | None = Field(default=None, gt=1)
    implied_probability_raw: float | None = Field(default=None, ge=0, le=1)
    no_vig_probability: float | None = Field(default=None, ge=0, le=1)
    overround: float | None = Field(default=None, ge=0)
    edge_raw: float | None = Field(default=None, ge=-1, le=1)
    edge_no_vig: float | None = Field(default=None, ge=-1, le=1)
    expected_value: float | None = Field(default=None, ge=-1)
    formula_version: str = Field(min_length=1)
    odds_observed_at: datetime | None
    prediction_cutoff_at: datetime | None
    quality: DataQuality

    @field_serializer("odds_observed_at", "prediction_cutoff_at")
    def _ts(self, value: datetime | None) -> str | None:
        return to_rfc3339(value) if value else None


class Pick(ApiModel):
    id: str = Field(min_length=1, max_length=128)
    match: MatchSummary
    market: str = Field(min_length=1)
    selection: str = Field(min_length=1)
    selection_label: str = Field(min_length=1)
    calibrated_probability: float | None = Field(default=None, ge=0, le=1)
    confidence: ConfidenceLevel
    rationale: str
    criteria: str
    model_version: str = Field(min_length=1)
    published_at: datetime
    quality: DataQuality

    @field_serializer("published_at")
    def _published(self, value: datetime) -> str:
        return to_rfc3339(value)


class Insight(ApiModel):
    id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1)
    body: str
    kind: InsightKind
    href: str | None
    quality: DataQuality


class MetricPoint(ApiModel):
    label: str
    value: float | None
    quality: DataQuality


class ModelHealthSummary(ApiModel):
    model_version: str = Field(min_length=1)
    sport: SportCode
    window_label: str = Field(min_length=1)
    accuracy: float | None = Field(default=None, ge=0, le=1)
    log_loss: float | None = Field(default=None, ge=0)
    brier_score: float | None = Field(default=None, ge=0, le=1)
    ece: float | None = Field(default=None, ge=0, le=1)
    theoretical_roi: float | None = Field(default=None, ge=-1)
    theoretical_max_drawdown: float | None = Field(default=None, ge=-1, le=0)
    prediction_count: int = Field(ge=0)
    quality: DataQuality


class DashboardSnapshot(ApiModel):
    headline: str
    sports: list[Sport]
    matches_today: list[MatchSummary]
    picks: list[Pick]
    value_opportunities: list[ValueOpportunity]
    insights: list[Insight]
    model_health: ModelHealthSummary


class PerformanceSeriesPoint(ApiModel):
    period: str
    log_loss: float | None = Field(default=None, ge=0)
    brier_score: float | None = Field(default=None, ge=0, le=1)
    accuracy: float | None = Field(default=None, ge=0, le=1)
    theoretical_roi: float | None = Field(default=None, ge=-1)


class CalibrationBucket(ApiModel):
    predicted: float = Field(ge=0, le=1)
    observed: float | None = Field(default=None, ge=0, le=1)
    count: int = Field(ge=0)


class PerformanceReport(ApiModel):
    summary: ModelHealthSummary
    series: list[PerformanceSeriesPoint]
    calibration: list[CalibrationBucket]
    notes: list[str]


class StandingRow(ApiModel):
    rank: int | None = Field(default=None, ge=1)
    team: Team
    played: int | None = Field(default=None, ge=0)
    points: int | None = None
    goal_diff: int | None = None
    quality: DataQuality


class LeagueDetail(ApiModel):
    league: League
    standing: list[StandingRow]
    recent_matches: list[MatchSummary]
    unavailable_fields: list[UnavailableField]


class TeamDetail(ApiModel):
    team: Team
    league: League
    recent_matches: list[MatchSummary]
    stats: list[NamedStat]
    unavailable_fields: list[UnavailableField]


class PlayerDetail(ApiModel):
    player: Player
    team: Team | None
    stats: list[NamedStat]
    recent_mentions: list[str]
    unavailable_fields: list[UnavailableField]


class Fact(ApiModel):
    id: str = Field(min_length=1, max_length=128)
    label: str
    value: str
    unit: str | None
    source: str = Field(min_length=1)
    observed_at: datetime
    availability: AvailabilityStatus

    @field_serializer("observed_at")
    def _observed(self, value: datetime) -> str:
        return to_rfc3339(value)


class FactPack(ApiModel):
    id: str = Field(min_length=1, max_length=128)
    match_id: str = Field(min_length=1, max_length=128)
    generated_at: datetime
    facts: list[Fact]

    @field_serializer("generated_at")
    def _generated(self, value: datetime) -> str:
        return to_rfc3339(value)


class AnalystMessage(ApiModel):
    id: str = Field(min_length=1, max_length=128)
    role: AnalystRole
    body: str
    cited_fact_ids: list[str]
    created_at: datetime

    @field_serializer("created_at")
    def _created(self, value: datetime) -> str:
        return to_rfc3339(value)


class AnalystSession(ApiModel):
    match_id: str = Field(min_length=1, max_length=128)
    fact_pack: FactPack
    messages: list[AnalystMessage]
    llm_model: str = Field(min_length=1)
    prompt_version: str = Field(min_length=1)
    disclaimer: str = Field(min_length=1)


class AnalystRequest(ApiModel):
    match_id: str = Field(min_length=1, max_length=128)
    question: str | None = Field(default=None, min_length=1, max_length=2000)


class ListResult[T](ApiModel):
    items: list[T]
    total: int = Field(ge=0)


class Envelope[T](EnvelopeMetadata):
    data: T


class FootballModelPrediction(ApiModel):
    """Calibrated 1X2 probabilities from a versioned football model. Never a certainty or bet."""

    match_id: str = Field(min_length=1, max_length=128)
    sport: Literal["football"] = "football"
    market: Literal["1X2"] = "1X2"
    home_probability: float = Field(gt=0, lt=1)
    draw_probability: float = Field(gt=0, lt=1)
    away_probability: float = Field(gt=0, lt=1)
    model_version: str = Field(min_length=1, max_length=128)
    dataset_version: str = Field(min_length=1, max_length=128)
    feature_schema_version: str = Field(min_length=1, max_length=128)
    model_status: FootballModelStatus
    cutoff_at: datetime
    cutoff_policy: str = Field(min_length=1, max_length=64)
    generated_at: datetime

    @field_serializer("cutoff_at", "generated_at")
    def _timestamps(self, value: datetime) -> str:
        return to_rfc3339(value)

    @model_validator(mode="after")
    def probabilities_form_simplex(self) -> Self:
        total = self.home_probability + self.draw_probability + self.away_probability
        if abs(total - 1.0) > 1e-9:
            raise ValueError("home_probability, draw_probability and away_probability must sum to 1.")
        return self
