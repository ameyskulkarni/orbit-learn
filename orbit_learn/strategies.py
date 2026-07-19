"""Pluggable scheduling strategies: Leitner (default), SM-2, FSRS. See design doc §16."""

from __future__ import annotations

import math
from datetime import date
from typing import ClassVar, Protocol, runtime_checkable

from orbit_learn.scheduler import (
    INITIAL_INTERVAL,
    MAX_INTERVAL,
    next_interval,
)


@runtime_checkable
class SchedulingStrategy(Protocol):
    """Per-topic scheduling policy. Competence (EWMA) is orthogonal — handled elsewhere."""

    name: ClassVar[str]

    def initial_state(self) -> dict: ...
    def update(self, state: dict, score: int, review_date: date) -> dict: ...
    def interval_days(self, state: dict) -> float: ...


# =============================================================================
# 1. Leitner + EWMA — the Phase-3 default. Wraps `scheduler.next_interval` so
#    the 37 existing tests continue to pass bit-for-bit.
# =============================================================================


class LeitnerEWMAStrategy:
    name: ClassVar[str] = "ewma"

    def initial_state(self) -> dict:
        return {"interval": INITIAL_INTERVAL}

    def update(self, state: dict, score: int, review_date: date) -> dict:
        return {"interval": next_interval(state["interval"], score)}

    def interval_days(self, state: dict) -> float:
        return float(state.get("interval", INITIAL_INTERVAL))


# =============================================================================
# 2. SM-2 — SuperMemo 2. Classic ease-factor + repetition + interval.
# =============================================================================

SM2_EF_DEFAULT: float = 2.5
SM2_EF_FLOOR: float = 1.3
SM2_MAX_INTERVAL_DAYS: float = 180.0


def _sm2_ef_delta(q: int) -> float:
    """SM-2 ease-factor delta for a grade q in 0..5. Matches reference table (design doc §16.4)."""
    return 0.1 - (5 - q) * (0.08 + (5 - q) * 0.02)


class SM2Strategy:
    name: ClassVar[str] = "sm2"

    def initial_state(self) -> dict:
        return {
            "ease_factor": SM2_EF_DEFAULT,
            "repetition": 0,
            "interval": 1.0,
        }

    def update(self, state: dict, score: int, review_date: date) -> dict:
        ef = float(state.get("ease_factor", SM2_EF_DEFAULT))
        rep = int(state.get("repetition", 0))
        interval = float(state.get("interval", 1.0))

        if score < 3:
            # Failure: reset the interval and repetition, but let the EF still update.
            new_interval = 1.0
            new_rep = 0
        else:
            new_rep = rep + 1
            if new_rep == 1:
                new_interval = 1.0
            elif new_rep == 2:
                new_interval = 6.0
            else:
                new_interval = interval * ef

        new_interval = min(new_interval, SM2_MAX_INTERVAL_DAYS)

        # EF always updates, floored at SM2_EF_FLOOR.
        new_ef = max(SM2_EF_FLOOR, ef + _sm2_ef_delta(score))

        return {"ease_factor": new_ef, "repetition": new_rep, "interval": new_interval}

    def interval_days(self, state: dict) -> float:
        return float(state.get("interval", 1.0))


# =============================================================================
# 3. FSRS — Free Spaced Repetition Scheduler (FSRS-4.5 with public defaults).
#
#    Complete FSRS-5 (21 weights + per-user calibration) is intentionally out of
#    scope. Users who need it can register a custom strategy that wraps the
#    upstream `fsrs` package.
# =============================================================================

FSRS_DECAY: float = -0.5
FSRS_FACTOR: float = 19.0 / 81.0
FSRS_TARGET_RETENTION: float = 0.9
FSRS_MAX_INTERVAL_DAYS: float = 365.0

FSRS_DEFAULT_W: tuple[float, ...] = (
    0.4197, 1.1869, 3.0412, 15.2441,   # 0..3   initial stability by rating (Again/Hard/Good/Easy)
    7.1434, 0.6477,                    # 4..5   initial difficulty base + rating slope
    1.0007, 0.0674,                    # 6..7   difficulty rating factor + mean-reversion weight
    1.6597, 0.1712,                    # 8..9   stability update (success): exp / power terms
    1.1178, 2.0225,                    # 10..11 stability update (success + lapse) — R exponent / lapse pre-factor
    0.0904, 0.3025,                    # 12..13 lapse difficulty & interval exponents
    2.1214, 0.2498, 2.9466,            # 14..16 lapse retrievability + Hard/Easy bonuses
)


def orbit_score_to_fsrs_rating(score: int) -> int:
    """Map Orbit's 1-5 self-score to FSRS rating: Again(1)/Hard(2)/Good(3)/Easy(4)."""
    if score <= 2:
        return 1
    if score == 3:
        return 2
    if score == 4:
        return 3
    return 4


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def stability_to_interval(
    stability: float,
    target_retention: float = FSRS_TARGET_RETENTION,
) -> float:
    """Convert stability to the days until retrievability decays to `target_retention`.

    R(t) = (1 + FACTOR * t / S) ^ DECAY. Solving for t at R = target gives
    t = (S / FACTOR) * (target ^ (1/DECAY) - 1).
    """
    return (stability / FSRS_FACTOR) * (target_retention ** (1.0 / FSRS_DECAY) - 1.0)


class FSRSStrategy:
    """FSRS-4.5-ish: tracks per-topic difficulty D and stability S."""

    name: ClassVar[str] = "fsrs"

    def initial_state(self) -> dict:
        return {"stability": None, "difficulty": None, "last_reviewed": None}

    def update(self, state: dict, score: int, review_date: date) -> dict:
        rating = orbit_score_to_fsrs_rating(score)
        W = FSRS_DEFAULT_W

        stability = state.get("stability")
        difficulty = state.get("difficulty")
        last_reviewed_iso = state.get("last_reviewed")

        if stability is None or difficulty is None or last_reviewed_iso is None:
            # First-ever review of this topic.
            new_stability = max(0.1, W[rating - 1])
            new_difficulty = _clamp(W[4] - math.exp(W[5] * (rating - 1)) + 1.0, 1.0, 10.0)
        else:
            last_reviewed = date.fromisoformat(last_reviewed_iso)
            elapsed = max(0, (review_date - last_reviewed).days)
            # Retrievability at the moment of review.
            R = (1.0 + FSRS_FACTOR * elapsed / stability) ** FSRS_DECAY

            # --- Difficulty update: shift by rating, then partial mean reversion. ---
            D_shift = difficulty - W[6] * (rating - 3)
            D_target = W[4] - math.exp(W[5] * (4 - 1)) + 1.0  # Reversion anchor = D_0(Easy).
            D_next = D_shift + W[7] * (D_target - D_shift)
            new_difficulty = _clamp(D_next, 1.0, 10.0)

            # --- Stability update — two branches per FSRS-4.5. ---
            if rating == 1:  # Again: a lapse.
                new_stability = (
                    W[11]
                    * (difficulty ** (-W[12]))
                    * (((stability + 1.0) ** W[13]) - 1.0)
                    * math.exp((1.0 - R) * W[14])
                )
                # A lapse never increases stability.
                new_stability = min(new_stability, stability)
            else:
                bonus = {2: W[15], 3: 1.0, 4: W[16]}[rating]
                new_stability = stability * (
                    1.0
                    + math.exp(W[8])
                    * (11.0 - new_difficulty)
                    * (stability ** (-W[9]))
                    * (math.exp((1.0 - R) * W[10]) - 1.0)
                    * bonus
                )

            new_stability = _clamp(new_stability, 0.1, FSRS_MAX_INTERVAL_DAYS)

        return {
            "stability": float(new_stability),
            "difficulty": float(new_difficulty),
            "last_reviewed": review_date.isoformat(),
        }

    def interval_days(self, state: dict) -> float:
        stability = state.get("stability")
        if stability is None:
            return 1.0
        raw = stability_to_interval(float(stability))
        return max(1.0, min(raw, FSRS_MAX_INTERVAL_DAYS))


# =============================================================================
# Factory
# =============================================================================

_STRATEGIES: dict[str, type[SchedulingStrategy]] = {
    LeitnerEWMAStrategy.name: LeitnerEWMAStrategy,
    SM2Strategy.name: SM2Strategy,
    FSRSStrategy.name: FSRSStrategy,
}


def get_strategy(name: str) -> SchedulingStrategy:
    """Instantiate a scheduling strategy by config name. Raises ValueError on unknown."""
    cls = _STRATEGIES.get(name)
    if cls is None:
        known = ", ".join(sorted(_STRATEGIES))
        raise ValueError(f"Unknown scoring_strategy {name!r}. Known: {known}.")
    return cls()


__all__ = [
    "SchedulingStrategy",
    "LeitnerEWMAStrategy",
    "SM2Strategy",
    "FSRSStrategy",
    "get_strategy",
    "orbit_score_to_fsrs_rating",
    "stability_to_interval",
    # Constants exposed for tests + config.
    "SM2_EF_DEFAULT",
    "SM2_EF_FLOOR",
    "SM2_MAX_INTERVAL_DAYS",
    "FSRS_DECAY",
    "FSRS_FACTOR",
    "FSRS_TARGET_RETENTION",
    "FSRS_MAX_INTERVAL_DAYS",
    "FSRS_DEFAULT_W",
]
