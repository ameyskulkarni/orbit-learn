"""Strategy factory + cross-strategy integration: all three strategies replay a common score history."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from orbit_learn.scheduler import INITIAL_INTERVAL, next_interval
from orbit_learn.strategies import (
    FSRSStrategy,
    LeitnerEWMAStrategy,
    SM2Strategy,
    SchedulingStrategy,
    get_strategy,
)

DAY0 = date(2026, 7, 1)
SCORES = [5, 4, 3, 5, 5, 1, 3, 4, 5, 5]


# --- Factory ---

def test_get_strategy_by_name():
    assert isinstance(get_strategy("ewma"), LeitnerEWMAStrategy)
    assert isinstance(get_strategy("sm2"), SM2Strategy)
    assert isinstance(get_strategy("fsrs"), FSRSStrategy)


def test_get_strategy_unknown_raises():
    with pytest.raises(ValueError):
        get_strategy("unknown-alg")


def test_all_strategies_declare_name():
    assert LeitnerEWMAStrategy.name == "ewma"
    assert SM2Strategy.name == "sm2"
    assert FSRSStrategy.name == "fsrs"


# --- Leitner strategy matches the existing Phase-3 primitives exactly ---

def test_leitner_strategy_matches_scheduler_primitives():
    """LeitnerEWMAStrategy must be bit-for-bit compatible with the pre-Phase-6 behavior."""
    strat = LeitnerEWMAStrategy()
    state = strat.initial_state()

    expected_interval = INITIAL_INTERVAL
    for i, s in enumerate(SCORES):
        state = strat.update(state, s, DAY0 + timedelta(days=i))
        expected_interval = next_interval(expected_interval, s)
        assert strat.interval_days(state) == pytest.approx(expected_interval)


# --- Cross-strategy: every strategy produces finite positive intervals ---

@pytest.mark.parametrize("strat_name", ["ewma", "sm2", "fsrs"])
def test_strategy_produces_valid_intervals_over_history(strat_name: str):
    strat: SchedulingStrategy = get_strategy(strat_name)
    state = strat.initial_state()
    day = DAY0
    for s in SCORES:
        state = strat.update(state, s, day)
        interval = strat.interval_days(state)
        assert interval > 0
        assert interval < 10_000
        day += timedelta(days=max(1, int(round(interval))))
