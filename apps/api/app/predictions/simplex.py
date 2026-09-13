from __future__ import annotations

import math

from app.predictions.types import PROBABILITY_CLIP, SIMPLEX_ATOL, OutcomeProbabilities


def renormalize_1x2(home: float, draw: float, away: float) -> OutcomeProbabilities:
    clipped = (
        min(1.0, max(PROBABILITY_CLIP, float(home))),
        min(1.0, max(PROBABILITY_CLIP, float(draw))),
        min(1.0, max(PROBABILITY_CLIP, float(away))),
    )
    total = clipped[0] + clipped[1] + clipped[2]
    if total <= 0.0 or not math.isfinite(total):
        raise ValueError("1X2 probabilities cannot be renormalized.")
    normalized = OutcomeProbabilities(home=clipped[0] / total, draw=clipped[1] / total, away=clipped[2] / total)
    if not math.isclose(normalized.total(), 1.0, abs_tol=SIMPLEX_ATOL, rel_tol=0.0):
        raise ValueError("Renormalized 1X2 probabilities do not sum to 1.")
    return normalized
