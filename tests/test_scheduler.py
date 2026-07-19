"""Spaced-repetition scheduler: interval progression + next-review date + review-urgency ramp."""

from __future__ import annotations

from datetime import date

import pytest

from orbit_learn.scheduler import (
    INITIAL_INTERVAL,
    MAX_INTERVAL,
    next_interval,
    next_review_date,
    review_urgency,
)


# --- next_interval: Leitner-style progression ---

def test_pass_doubles_interval():
    assert next_interval(1.0, 4) == 2.0
    assert next_interval(2.0, 5) == 4.0
    assert next_interval(4.0, 4) == 8.0


def test_okay_score_preserves_interval():
    # A score of 3 means "same interval" — no punishment, no reward.
    assert next_interval(4.0, 3) == 4.0
    assert next_interval(1.0, 3) == 1.0


def test_failing_score_resets_to_initial():
    assert next_interval(16.0, 2) == INITIAL_INTERVAL
    assert next_interval(16.0, 1) == INITIAL_INTERVAL
    assert next_interval(0.5, 0) == INITIAL_INTERVAL


def test_interval_capped_at_max():
    assert next_interval(20.0, 5) == MAX_INTERVAL
    assert next_interval(30.0, 5) == MAX_INTERVAL
    # Score of 3 preserves 30 as well
    assert next_interval(30.0, 3) == MAX_INTERVAL


# --- next_review_date ---

def test_next_review_date_adds_integer_days():
    d = date(2026, 7, 18)
    assert next_review_date(d, 1.0) == date(2026, 7, 19)
    assert next_review_date(d, 5.0) == date(2026, 7, 23)
    assert next_review_date(d, 30.0) == date(2026, 8, 17)


def test_next_review_date_rounds_fractional_interval():
    d = date(2026, 7, 18)
    # 1.5 rounds to 2 (banker's rounding by round()).
    assert next_review_date(d, 1.4) == date(2026, 7, 19)
    assert next_review_date(d, 1.6) == date(2026, 7, 20)


# --- review_urgency: linear ramp in the 2 days before due ---

def test_review_urgency_none_next_review_is_zero():
    assert review_urgency(None, date(2026, 7, 18)) == 0.0


def test_review_urgency_past_due_is_one():
    assert review_urgency(date(2026, 7, 15), date(2026, 7, 18)) == 1.0


def test_review_urgency_due_today_is_one():
    assert review_urgency(date(2026, 7, 18), date(2026, 7, 18)) == 1.0


def test_review_urgency_ramps_linearly_over_2_days():
    today = date(2026, 7, 18)
    # 1 day out → half urgency
    assert review_urgency(date(2026, 7, 19), today) == pytest.approx(0.5)
    # 2 days out → no urgency yet
    assert review_urgency(date(2026, 7, 20), today) == pytest.approx(0.0)
    # 3+ days out → still no urgency
    assert review_urgency(date(2026, 7, 21), today) == pytest.approx(0.0)
