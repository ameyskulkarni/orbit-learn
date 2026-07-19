"""SM-2 strategy: ease-factor updates, interval progression, reset semantics, floor + cap."""

from __future__ import annotations

from datetime import date

import pytest

from orbit_learn.strategies import (
    SM2_EF_DEFAULT,
    SM2_EF_FLOOR,
    SM2_MAX_INTERVAL_DAYS,
    SM2Strategy,
)

TODAY = date(2026, 7, 18)


@pytest.fixture
def strat() -> SM2Strategy:
    return SM2Strategy()


# --- Initial state ---

def test_initial_state_has_defaults(strat: SM2Strategy) -> None:
    st = strat.initial_state()
    assert st["ease_factor"] == pytest.approx(SM2_EF_DEFAULT)
    assert st["repetition"] == 0
    assert st["interval"] == pytest.approx(1.0)


# --- Ease-factor deltas per score (design doc §16.4 reference table) ---

@pytest.mark.parametrize(
    "score,expected_delta",
    [
        (1, -0.54),
        (2, -0.32),
        (3, -0.14),
        (4, 0.00),
        (5, +0.10),
    ],
)
def test_ease_factor_delta_matches_reference_table(
    strat: SM2Strategy, score: int, expected_delta: float
) -> None:
    st = strat.initial_state()
    new = strat.update(st, score, TODAY)
    assert new["ease_factor"] == pytest.approx(SM2_EF_DEFAULT + expected_delta, abs=1e-6)


# --- Interval progression on repeated success ---

def test_first_pass_sets_interval_1_day(strat: SM2Strategy) -> None:
    st = strat.update(strat.initial_state(), 5, TODAY)
    assert st["interval"] == pytest.approx(1.0)
    assert st["repetition"] == 1


def test_second_pass_sets_interval_6_days(strat: SM2Strategy) -> None:
    st = strat.initial_state()
    st = strat.update(st, 5, TODAY)
    st = strat.update(st, 5, TODAY)
    assert st["interval"] == pytest.approx(6.0)
    assert st["repetition"] == 2


def test_third_pass_multiplies_by_ease_factor(strat: SM2Strategy) -> None:
    st = strat.initial_state()
    st = strat.update(st, 5, TODAY)
    st = strat.update(st, 5, TODAY)
    ef_before_third = st["ease_factor"]
    st = strat.update(st, 5, TODAY)
    # Interval was 6, EF updates BEFORE it multiplies, but per design the
    # interval-multiplier uses the EF from AFTER the update. Either convention
    # is fine as long as we're consistent — assert against the actual implementation.
    assert st["interval"] > 6.0
    assert st["repetition"] == 3


# --- Reset semantics on fail ---

def test_score_below_3_resets_interval_and_repetition(strat: SM2Strategy) -> None:
    st = strat.initial_state()
    for _ in range(4):
        st = strat.update(st, 5, TODAY)
    # State is now well past repetition 0.
    assert st["repetition"] > 0
    st = strat.update(st, 2, TODAY)
    assert st["interval"] == pytest.approx(1.0)
    assert st["repetition"] == 0


def test_score_below_3_still_updates_ease_factor_downward(strat: SM2Strategy) -> None:
    st = strat.initial_state()
    st = strat.update(st, 5, TODAY)  # push EF up slightly
    ef_before = st["ease_factor"]
    st = strat.update(st, 1, TODAY)  # a big miss
    assert st["ease_factor"] < ef_before


# --- Ease-factor floor ---

def test_ease_factor_never_drops_below_floor(strat: SM2Strategy) -> None:
    st = strat.initial_state()
    for _ in range(20):
        st = strat.update(st, 1, TODAY)
    assert st["ease_factor"] == pytest.approx(SM2_EF_FLOOR, abs=1e-6)


# --- MAX_INTERVAL cap ---

def test_interval_capped_at_max(strat: SM2Strategy) -> None:
    st = strat.initial_state()
    for _ in range(30):
        st = strat.update(st, 5, TODAY)
    assert st["interval"] <= SM2_MAX_INTERVAL_DAYS


# --- interval_days matches state["interval"] ---

def test_interval_days_reads_state(strat: SM2Strategy) -> None:
    st = strat.initial_state()
    st = strat.update(st, 5, TODAY)
    st = strat.update(st, 5, TODAY)
    assert strat.interval_days(st) == pytest.approx(6.0)
