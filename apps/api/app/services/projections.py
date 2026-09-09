from app.schemas import MatchDetail, MatchSummary, PredictionPreview


def to_match_summary(match: MatchDetail) -> MatchSummary:
    return MatchSummary(
        id=match.id,
        sport=match.sport,
        league=match.league,
        home=match.home,
        away=match.away,
        kickoff_at=match.kickoff_at,
        status=match.status,
        venue=match.venue,
        score=match.score,
        prediction_preview=match.prediction_preview,
        value_preview=match.value_preview,
        quality=match.quality,
    )


def leading_preview(match: MatchDetail) -> PredictionPreview | None:
    return match.prediction_preview
