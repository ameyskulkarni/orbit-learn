"""FSRS strategy: initial state by rating, monotonicity, difficulty bounds, retrievability math."""

from __future__ import annotations

import math
from datetime import date, timedelta

import pytest

from orbit_learn.strategies import (
    FSRS_DECAY,
    FSRS_DEFAULT_W,
    FSRS_FACTOR,
    FSRS_MAX_INTERVAL_DAYS,
    FSRS_TARGET_RETENTION,
    FSRSStrategy,
    orbit_score_to_fsrs_rating,
)

DAY0 = date(2026, 7, 1)


@pytest.fixture
def strat() -> FSRSStrategy:
    return FSRSStrategy()


# --- Grade mapping (design doc §16.5) ---

@pytest.mark.parametrize(
    "score,expected_rating",
    [
        (1, 1),   # Again
        (2, 1),   # Again
        (3, 2),   # Hard
        (4, 3),   # Good
        (5, 4),   # Easy
    ],
)
def test_orbit_score_maps_to_fsrs_rating(score: int, expected_rating: int) -> None:
    assert orbit_score_to_fsrs_rating(score) == expected_rating


# --- Initial state before first review ---

def test_initial_state_is_empty(strat: FSRSStrategy) -> None:
    st = strat.initial_state()
    assert st["stability"] is None
    assert st["difficulty"] is None
    assert st["last_reviewed"] is None


# --- First-review stability by rating (public FSRS-4.5 weights) ---

@pytest.mark.parametrize(
    "score,expected_stability",
    [
        (1, FSRS_DEFAULT_W[0]),   # Again
        (3, FSRS_DEFAULT_W[1]),   # Hard
        (4, FSRS_DEFAULT_W[2]),   # Good
        (5, FSRS_DEFAULT_W[3]),   # Easy
    ],
)
def test_first_review_stability_matches_pretrained_weights(
    strat: FSRSStrategy, score: int, expected_stability: float
) -> None:
    st = strat.update(strat.initial_state(), score, DAY0)
    assert st["stability"] == pytest.approx(expected_stability, rel=1e-6)


def test_first_review_difficulty_in_valid_range(strat: FSRSStrategy) -> None:
    for score in (1, 2, 3, 4, 5):
        st = strat.update(strat.initial_state(), score, DAY0)
        assert 1.0 <= st["difficulty"] <= 10.0


def test_first_review_records_review_date(strat: FSRSStrategy) -> None:
    st = strat.update(strat.initial_state(), 4, DAY0)
    assert st["last_reviewed"] == DAY0.isoformat()


# --- Monotonicity: repeated success grows stability ---

def test_repeated_good_scores_grow_stability(strat: FSRSStrategy) -> None:
    """Reviewing at each new interval boundary — stability should grow with each success.

    Kept short (3 iterations) because FSRS-4.5's stability compounds quickly under Good
    scores; a longer chain saturates at FSRS_MAX_INTERVAL_DAYS and breaks strict growth.
    """
    st = strat.initial_state()
    day = DAY0
    st = strat.update(st, 4, day)
    stabilities = [st["stability"]]
    for _ in range(3):
        day += timedelta(days=max(1, int(round(strat.interval_days(st)))))
        st = strat.update(st, 4, day)
        stabilities.append(st["stability"])
    assert all(b > a for a, b in zip(stabilities, stabilities[1:]))


def test_again_shrinks_or_holds_stability(strat: FSRSStrategy) -> None:
    st = strat.initial_state()
    # Build up some stability first.
    st = strat.update(st, 5, DAY0)
    st = strat.update(st, 5, DAY0 + timedelta(days=15))
    st_before = st["stability"]
    # Now a lapse.
    st = strat.update(st, 1, DAY0 + timedelta(days=45))
    assert st["stability"] <= st_before + 1e-9   # allow FP wobble


# --- Difficulty bounds always hold ---

def test_difficulty_stays_in_1_10_across_many_updates(strat: FSRSStrategy) -> None:
    st = strat.initial_state()
    day = DAY0
    scores = [5, 4, 3, 1, 5, 5, 2, 4, 5, 1, 3, 4, 5, 5, 1, 1, 5, 4, 3, 2]
    for s in scores:
        st = strat.update(st, s, day)
        assert 1.0 <= st["difficulty"] <= 10.0
        day += timedelta(days=max(1, int(round(strat.interval_days(st)))))


# --- Retrievability sanity: at elapsed = stability, R equals target retention ---

def test_retrievability_at_stability_equals_target():
    """R(t=S) = (1 + FACTOR)^DECAY. With FACTOR=19/81 and DECAY=-0.5 that's ~0.9."""
    r = (1.0 + FSRS_FACTOR) ** FSRS_DECAY
    assert r == pytest.approx(FSRS_TARGET_RETENTION, abs=1e-4)


# --- interval_days ≈ stability when TARGET_RETENTION = 0.9 ---

def test_interval_days_approximately_equals_stability(strat: FSRSStrategy) -> None:
    st = strat.update(strat.initial_state(), 4, DAY0)  # Good → S = W[2]
    assert strat.interval_days(st) == pytest.approx(st["stability"], rel=0.05)


def test_interval_days_capped_at_max(strat: FSRSStrategy) -> None:
    st = strat.initial_state()
    day = DAY0
    for _ in range(20):
        st = strat.update(st, 5, day)  # Easy every time
        day += timedelta(days=max(1, int(round(strat.interval_days(st)))))
    assert strat.interval_days(st) <= FSRS_MAX_INTERVAL_DAYS


def test_interval_days_cold_start_is_positive(strat: FSRSStrategy) -> None:
    assert strat.interval_days(strat.initial_state()) >= 1.0
