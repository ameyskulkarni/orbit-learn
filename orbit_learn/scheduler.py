"""Spaced-repetition primitives: per-topic interval progression and review-urgency scoring.

This is the simplified Leitner system described in design doc §7.6. It's the default
scheduling strategy (wrapped as `LeitnerEWMAStrategy` in orbit_learn.strategies), and
also supplies the `next_review_date` helper used by SM-2 and FSRS to place their
computed intervals on the calendar.
"""

from __future__ import annotations

from datetime import date, timedelta

INITIAL_INTERVAL: float = 1.0    # See the topic again tomorrow after a fail or first exposure.
MAX_INTERVAL: float = 30.0       # Cap to prevent topics from disappearing entirely.


def next_interval(current_interval: float, score: int) -> float:
    """Update the review interval based on the latest score.

    - score >= 4 (passed):   double the interval (up to MAX_INTERVAL).
    - score >= 3 (okay):     keep the same interval.
    - else (failed):         reset to INITIAL_INTERVAL.
    """
    if score >= 4:
        return min(MAX_INTERVAL, current_interval * 2.0)
    if score >= 3:
        return min(MAX_INTERVAL, current_interval)
    return INITIAL_INTERVAL


def next_review_date(today: date, interval_days: float) -> date:
    """Return today + `interval_days` (rounded to the nearest integer day)."""
    return today + timedelta(days=int(round(interval_days)))


def review_urgency(next_review: date | None, today: date) -> float:
    """0.0 → 1.0 scalar for how urgent a review is, feeding into the topic-priority formula.

    - `None` (never reviewed): 0.0.
    - >= 2 days before due:    0.0.
    - Linear ramp from 0.0 → 1.0 across the 2 days before the review date.
    - Due today or overdue:    1.0.
    """
    if next_review is None:
        return 0.0
    days_until = (next_review - today).days
    if days_until <= 0:
        return 1.0
    if days_until >= 2:
        return 0.0
    return 1.0 - days_until / 2.0
