"""Adaptive scoring engine: EWMA competence, difficulty tracking, topic priority, mode selection.

All decisions about what/how to teach next are made by this module. The LLM only ever
decides how to *express* items — never which topics or difficulty to cover.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta
from typing import Literal

from src.models import ItemAssignment, SubjectConfig
from src.scheduler import review_urgency

# --- Tunables (design doc §7 defaults) ---

EWMA_ALPHA: float = 0.30

DIFFICULTY_STEP_UP: float = 0.20        # avg_score >= 4
DIFFICULTY_STEP_DOWN: float = 0.30      # avg_score <= 2  — drops faster than it rises
DIFFICULTY_MID_SLOPE: float = 0.10      # per point of (avg_score - 3.0)
DIFFICULTY_MIN: float = 1.0
DIFFICULTY_MAX: float = 5.0

PRIORITY_WEIGHTS: dict[str, float] = {
    "weakness": 0.35,
    "recency": 0.25,
    "spaced_rep": 0.25,
    "novelty": 0.10,
    "fatigue": 0.05,
}
RECENCY_SATURATION_DAYS: float = 7.0    # After a week unseen, recency contribution is maxed.
REMEDIATION_BOOST: float = 0.50

Mode = Literal["practice", "teach_then_practice", "review"]


# ============================================================================
# Pure functions — deterministic, testable without any DB or LLM.
# ============================================================================


def next_competence(
    old_competence: float,
    latest_score: int,
    is_first: bool = False,
    alpha: float = EWMA_ALPHA,
) -> float:
    """EWMA update. First score becomes the initial competence (cold-start rule)."""
    if is_first:
        return float(latest_score)
    return alpha * latest_score + (1.0 - alpha) * old_competence


def next_difficulty(current_difficulty: float, avg_session_score: float) -> float:
    """Adjust the track-wide difficulty float based on the last session's average score."""
    if avg_session_score >= 4.0:
        current_difficulty += DIFFICULTY_STEP_UP
    elif avg_session_score <= 2.0:
        current_difficulty -= DIFFICULTY_STEP_DOWN
    else:
        current_difficulty += (avg_session_score - 3.0) * DIFFICULTY_MID_SLOPE
    return max(DIFFICULTY_MIN, min(DIFFICULTY_MAX, current_difficulty))


def topic_priority(
    competence: float,
    days_since_last_seen: float,
    spaced_rep_urgency: float,
    times_seen: int,
    times_seen_this_week: int,
    needs_remediation: bool = False,
    weights: dict[str, float] | None = None,
) -> float:
    """Rank topics for next-session selection. Higher = more urgent."""
    w = weights or PRIORITY_WEIGHTS
    weakness = 1.0 - competence / 5.0
    recency = min(days_since_last_seen / RECENCY_SATURATION_DAYS, 1.0)
    novelty = 1.0 if times_seen == 0 else 0.0
    p = (
        w["weakness"] * weakness
        + w["recency"] * recency
        + w["spaced_rep"] * spaced_rep_urgency
        + w["novelty"] * novelty
        - w["fatigue"] * times_seen_this_week
    )
    if needs_remediation:
        p += REMEDIATION_BOOST
    return p


def determine_mode(
    times_seen: int,
    needs_remediation: bool,
    competence: float,
    spaced_rep_urgency: float,
    mastered_threshold: float = 3.5,
) -> Mode:
    """Decide how the LLM should treat a topic: teach + practice, plain practice, or review."""
    if times_seen == 0 or needs_remediation:
        return "teach_then_practice"
    if competence >= mastered_threshold and spaced_rep_urgency > 0.0:
        return "review"
    return "practice"


def item_difficulty(track_difficulty: float, needs_remediation: bool = False) -> int:
    """Round the track's floating-point difficulty to an integer 1-5, dropping 1 for remediation."""
    d = int(round(track_difficulty))
    if needs_remediation:
        d -= 1
    return max(1, min(5, d))


def is_needs_remediation_from_scores(scores_newest_first: list[int]) -> bool:
    """Given a topic's scores newest-first, return True if remediation is currently active.

    Rules (design doc §7.5):
    - A score < 2 activates remediation.
    - A score >= 3 clears remediation.
    - A score of 2 neither activates nor clears — remediation persists through it.
    """
    for s in scores_newest_first:
        if s >= 3:
            return False
        if s < 2:
            return True
    return False


# ============================================================================
# Persistence-aware planners — used by the CLI to pick the next session.
# ============================================================================


def _recent_scores(conn: sqlite3.Connection, track: str, topic: str, limit: int = 10) -> list[int]:
    rows = conn.execute(
        """
        SELECT i.user_score AS score
          FROM items i JOIN sessions s ON i.session_id = s.id
         WHERE s.track = ? AND i.topic = ? AND i.user_score IS NOT NULL
         ORDER BY i.scored_at DESC
         LIMIT ?
        """,
        (track, topic, limit),
    ).fetchall()
    return [r["score"] for r in rows]


def _times_seen_this_week(
    conn: sqlite3.Connection, track: str, topic: str, today: date
) -> int:
    week_ago = today - timedelta(days=7)
    row = conn.execute(
        """
        SELECT COUNT(*) AS n
          FROM items i JOIN sessions s ON i.session_id = s.id
         WHERE s.track = ? AND i.topic = ? AND s.date >= ?
        """,
        (track, topic, week_ago.isoformat()),
    ).fetchone()
    return int(row["n"])


def plan_session(
    conn: sqlite3.Connection,
    subject: SubjectConfig,
    track: str,
    items_per_session: int,
    track_difficulty: float,
    today: date | None = None,
) -> list[ItemAssignment]:
    """Rank all topics by priority, pick top-N, assign a mode + difficulty + item_type to each."""
    today = today or date.today()

    stats_rows = conn.execute(
        "SELECT topic, competence, times_seen, last_seen, next_review "
        "  FROM topic_stats WHERE track = ?",
        (track,),
    ).fetchall()
    stats_by_topic = {r["topic"]: r for r in stats_rows}

    ranked: list[tuple[float, str, Mode, int]] = []
    for topic in subject.topics:
        row = stats_by_topic.get(topic)
        if row is not None:
            competence = float(row["competence"] or 0.0)
            times_seen = int(row["times_seen"] or 0)
            last_seen_iso = row["last_seen"]
            next_review = (
                date.fromisoformat(row["next_review"]) if row["next_review"] else None
            )
            days_since = (
                (today - date.fromisoformat(last_seen_iso[:10])).days
                if last_seen_iso
                else 999
            )
            urgency = review_urgency(next_review, today)
            needs_rem = is_needs_remediation_from_scores(
                _recent_scores(conn, track, topic)
            )
            fatigue = _times_seen_this_week(conn, track, topic, today)
        else:
            competence = 0.0
            times_seen = 0
            days_since = 999
            urgency = 0.0
            needs_rem = False
            fatigue = 0

        prio = topic_priority(
            competence=competence,
            days_since_last_seen=days_since,
            spaced_rep_urgency=urgency,
            times_seen=times_seen,
            times_seen_this_week=fatigue,
            needs_remediation=needs_rem,
        )
        mode = determine_mode(times_seen, needs_rem, competence, urgency)
        diff = item_difficulty(track_difficulty, needs_remediation=needs_rem)
        ranked.append((prio, topic, mode, diff))

    ranked.sort(key=lambda x: -x[0])
    picked = ranked[:items_per_session]

    types = list(subject.session_shape.keys())
    if not types:
        raise ValueError("Subject SESSION_SHAPE has no item_types.")

    assignments: list[ItemAssignment] = []
    for i, (_prio, topic, mode, diff) in enumerate(picked):
        assignments.append(
            ItemAssignment(
                topic=topic,
                item_type=types[i % len(types)],
                difficulty=diff,
                mode=mode,
            )
        )
    return assignments


def calibration_assignments(subject: SubjectConfig, items: int) -> list[ItemAssignment]:
    """First-run calibration: spread items evenly across topics at rising difficulties 1..5."""
    if items <= 0:
        return []
    if not subject.topics:
        raise ValueError("Subject TOPICS is empty; nothing to calibrate.")

    types = list(subject.session_shape.keys())
    if not types:
        raise ValueError("Subject SESSION_SHAPE has no item_types.")

    # Space the topics evenly across the subject list so we sample the domain.
    step = max(1, len(subject.topics) // items)
    picked = [subject.topics[(i * step) % len(subject.topics)] for i in range(items)]

    # Difficulty sweep: 1, 2, 3, ... capped at 5. If items > 5, saturate the tail at 5.
    difficulties = [min(5, i + 1) for i in range(items)]

    return [
        ItemAssignment(
            topic=topic,
            item_type=types[i % len(types)],
            difficulty=difficulties[i],
            mode="practice",
        )
        for i, topic in enumerate(picked)
    ]
