"""Scoring engine: EWMA competence, difficulty adjustment, topic priority, mode selection, remediation."""

from __future__ import annotations

import pytest

from src.scoring import (
    determine_mode,
    is_needs_remediation_from_scores,
    item_difficulty,
    next_competence,
    next_difficulty,
    topic_priority,
)


# --- EWMA competence (design doc §7.1) ---

def test_first_score_becomes_competence():
    assert next_competence(0.0, 4, is_first=True) == 4.0
    assert next_competence(0.0, 1, is_first=True) == 1.0


def test_subsequent_scores_apply_ewma_with_alpha_0_3():
    # 0.3 * 2 + 0.7 * 4 = 3.4
    assert next_competence(4.0, 2) == pytest.approx(3.4)
    # 0.3 * 5 + 0.7 * 3.0 = 3.6
    assert next_competence(3.0, 5) == pytest.approx(3.6)


def test_ewma_stays_within_score_range():
    # With alpha in [0,1] and scores in [1,5], competence stays bounded.
    c = 0.0
    for score in [5, 1, 3, 4, 2, 5, 5, 1]:
        c = next_competence(c, score)
    assert 0.0 <= c <= 5.0


# --- Difficulty adjustment (design doc §7.3) ---

def test_high_avg_raises_difficulty_by_0_2():
    assert next_difficulty(3.0, 4.0) == pytest.approx(3.2)
    assert next_difficulty(3.0, 4.9) == pytest.approx(3.2)


def test_low_avg_drops_difficulty_by_0_3():
    # Design doc: drop faster than rise
    assert next_difficulty(3.0, 2.0) == pytest.approx(2.7)
    assert next_difficulty(3.0, 1.0) == pytest.approx(2.7)


def test_mid_range_applies_linear_offset():
    # avg=3 → no change; avg=3.5 → +0.05; avg=2.5 → -0.05
    assert next_difficulty(3.0, 3.0) == pytest.approx(3.0)
    assert next_difficulty(3.0, 3.5) == pytest.approx(3.05)
    assert next_difficulty(3.0, 2.5) == pytest.approx(2.95)


def test_difficulty_clamped_to_1_5():
    assert next_difficulty(1.0, 1.0) == 1.0
    assert next_difficulty(5.0, 5.0) == 5.0
    assert next_difficulty(0.5, 3.0) == 1.0
    assert next_difficulty(5.5, 3.0) == 5.0


# --- Topic priority (design doc §7.2) ---

def _default_kwargs(**overrides) -> dict:
    base = {
        "competence": 3.0,
        "days_since_last_seen": 1.0,
        "spaced_rep_urgency": 0.0,
        "times_seen": 5,
        "times_seen_this_week": 0,
        "needs_remediation": False,
    }
    base.update(overrides)
    return base


def test_weaker_topics_have_higher_priority():
    p_weak = topic_priority(**_default_kwargs(competence=1.0))
    p_strong = topic_priority(**_default_kwargs(competence=5.0))
    assert p_weak > p_strong


def test_novelty_boosts_never_seen_topics():
    # A never-seen topic (times_seen=0) should beat a well-covered strong topic.
    p_new = topic_priority(**_default_kwargs(competence=0.0, times_seen=0, days_since_last_seen=0))
    p_seen = topic_priority(**_default_kwargs(competence=5.0, times_seen=10, days_since_last_seen=0))
    assert p_new > p_seen


def test_recency_boost_grows_with_time():
    p_fresh = topic_priority(**_default_kwargs(days_since_last_seen=0))
    p_old = topic_priority(**_default_kwargs(days_since_last_seen=14))
    assert p_old > p_fresh


def test_spaced_rep_urgency_boosts_priority():
    p_due = topic_priority(**_default_kwargs(spaced_rep_urgency=1.0))
    p_not_due = topic_priority(**_default_kwargs(spaced_rep_urgency=0.0))
    assert p_due > p_not_due


def test_fatigue_penalty_reduces_priority():
    p_fresh = topic_priority(**_default_kwargs(times_seen_this_week=0))
    p_fatigued = topic_priority(**_default_kwargs(times_seen_this_week=5))
    assert p_fresh > p_fatigued


def test_remediation_adds_flat_boost_of_0_5():
    kwargs = _default_kwargs(competence=2.0)
    p_normal = topic_priority(**kwargs)
    kwargs["needs_remediation"] = True
    p_remed = topic_priority(**kwargs)
    assert p_remed == pytest.approx(p_normal + 0.5)


# --- Mode selection (drives teach_then_practice / practice / review) ---

def test_mode_never_seen_is_teach_then_practice():
    assert determine_mode(
        times_seen=0, needs_remediation=False, competence=0.0, spaced_rep_urgency=0.0
    ) == "teach_then_practice"


def test_mode_remediation_is_teach_then_practice():
    assert determine_mode(
        times_seen=5, needs_remediation=True, competence=1.5, spaced_rep_urgency=0.0
    ) == "teach_then_practice"


def test_mode_mastered_and_review_due_is_review():
    assert determine_mode(
        times_seen=10, needs_remediation=False, competence=4.2, spaced_rep_urgency=1.0
    ) == "review"


def test_mode_mastered_but_not_due_is_practice():
    # High competence but review isn't due yet — no need to review.
    assert determine_mode(
        times_seen=10, needs_remediation=False, competence=4.5, spaced_rep_urgency=0.0
    ) == "practice"


def test_mode_default_is_practice():
    assert determine_mode(
        times_seen=5, needs_remediation=False, competence=3.0, spaced_rep_urgency=0.0
    ) == "practice"


# --- Item difficulty (remediation drops by 1 level, clamped 1-5) ---

def test_item_difficulty_rounds_from_track_difficulty():
    assert item_difficulty(3.2, needs_remediation=False) == 3
    assert item_difficulty(4.6, needs_remediation=False) == 5
    assert item_difficulty(1.2, needs_remediation=False) == 1


def test_item_difficulty_drops_by_1_on_remediation():
    assert item_difficulty(3.0, needs_remediation=True) == 2
    assert item_difficulty(5.0, needs_remediation=True) == 4


def test_item_difficulty_remediation_clamped_at_1():
    assert item_difficulty(1.0, needs_remediation=True) == 1
    assert item_difficulty(0.5, needs_remediation=True) == 1


# --- Remediation detection from score history ---

def test_remediation_false_on_empty_history():
    assert is_needs_remediation_from_scores([]) is False


def test_remediation_true_when_latest_score_below_2():
    assert is_needs_remediation_from_scores([1]) is True
    assert is_needs_remediation_from_scores([1, 5, 5]) is True


def test_remediation_cleared_by_score_of_3_or_higher():
    # A score >= 3 anywhere after the failure clears the flag.
    assert is_needs_remediation_from_scores([3, 1]) is False
    assert is_needs_remediation_from_scores([5, 1]) is False


def test_remediation_persists_through_middling_2():
    # A score of 2 is not a "trigger" and not a "clear" — the previous 1 keeps remediation on.
    assert is_needs_remediation_from_scores([2, 1]) is True
    assert is_needs_remediation_from_scores([2, 2, 1]) is True


def test_remediation_middling_2_alone_does_not_trigger():
    # Only scores < 2 activate remediation, so a bare [2] is not remediation.
    assert is_needs_remediation_from_scores([2]) is False


def test_remediation_intercalated_clear_then_new_fail_triggers_again():
    # Chronologically: fail(1), clear(3), fail(1) → newest-first: [1, 3, 1]
    # The most recent 1 puts us back in remediation.
    assert is_needs_remediation_from_scores([1, 3, 1]) is True
