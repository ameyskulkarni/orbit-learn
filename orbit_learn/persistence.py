"""SQLite persistence for sessions, items, and topic stats. One database file per track."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import date as date_type
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterator

from orbit_learn.models import Item, Session
from orbit_learn.scheduler import next_review_date
from orbit_learn.scoring import next_competence
from orbit_learn.strategies import LeitnerEWMAStrategy, SchedulingStrategy

DB_ROOT = Path("data")

# Schema mirrors design doc §6. `IF NOT EXISTS` makes init_db idempotent.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,
    track       TEXT NOT NULL,
    date        TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    difficulty  REAL NOT NULL,
    raw_json    TEXT
);
CREATE INDEX IF NOT EXISTS ix_sessions_track_date ON sessions(track, date);

CREATE TABLE IF NOT EXISTS items (
    id              TEXT PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES sessions(id),
    topic           TEXT NOT NULL,
    item_type       TEXT NOT NULL,
    difficulty      INTEGER NOT NULL,
    question        TEXT NOT NULL,
    expected_answer TEXT,
    user_score      INTEGER,
    llm_judge_score INTEGER,
    user_answer     TEXT,
    scored_at       TEXT
);
CREATE INDEX IF NOT EXISTS ix_items_session ON items(session_id);
CREATE INDEX IF NOT EXISTS ix_items_topic ON items(topic);

CREATE TABLE IF NOT EXISTS topic_stats (
    track           TEXT NOT NULL,
    topic           TEXT NOT NULL,
    competence      REAL NOT NULL DEFAULT 0.0,
    times_seen      INTEGER NOT NULL DEFAULT 0,
    times_correct   INTEGER NOT NULL DEFAULT 0,
    last_seen       TEXT,
    current_streak  INTEGER NOT NULL DEFAULT 0,
    next_review     TEXT,
    review_interval REAL NOT NULL DEFAULT 1.0,
    strategy_state  TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (track, topic)
);

CREATE TABLE IF NOT EXISTS calibration (
    track           TEXT NOT NULL,
    topic           TEXT NOT NULL,
    initial_score   INTEGER NOT NULL,
    calibrated_at   TEXT NOT NULL,
    PRIMARY KEY (track, topic)
);
"""


def db_path(track_name: str) -> Path:
    return DB_ROOT / f"{track_name}.db"


@contextmanager
def open_db(track_name: str) -> Iterator[sqlite3.Connection]:
    """Open (and initialize if needed) the SQLite database for a track."""
    path = db_path(track_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA)
    _migrate(conn)
    conn.commit()
    try:
        yield conn
    finally:
        conn.close()


def _migrate(conn: sqlite3.Connection) -> None:
    """Idempotent forward migrations. Safe on both new and Phase-3 databases."""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(topic_stats)")}
    # Phase 6: pluggable scheduling strategies need per-topic opaque JSON state.
    if "strategy_state" not in cols:
        conn.execute(
            "ALTER TABLE topic_stats ADD COLUMN strategy_state TEXT NOT NULL DEFAULT '{}'"
        )


def save_session(
    conn: sqlite3.Connection,
    session: Session,
    track: str,
    difficulty: float,
    raw_json: str | None = None,
) -> str:
    """Insert the session and its items. Returns the session id (already on the model)."""
    created_at = datetime.now().isoformat(timespec="microseconds")
    conn.execute(
        "INSERT INTO sessions (id, track, date, created_at, difficulty, raw_json) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (session.id, track, session.date, created_at, difficulty, raw_json),
    )
    for item in session.items:
        conn.execute(
            "INSERT INTO items "
            "(id, session_id, topic, item_type, difficulty, question, expected_answer) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                item.id,
                session.id,
                item.topic,
                item.item_type,
                item.difficulty,
                item.question,
                item.expected_answer,
            ),
        )
    conn.commit()
    return session.id


def record_score(
    conn: sqlite3.Connection,
    item_id: str,
    user_score: int,
    user_answer: str | None = None,
) -> None:
    """Store the learner's self-score (1-5) and optional free-text answer for a single item."""
    # Microseconds precision so rapid consecutive scores (scripted or test-driven) still
    # order deterministically in refresh_topic_stats' ORDER BY scored_at.
    scored_at = datetime.now().isoformat(timespec="microseconds")
    conn.execute(
        "UPDATE items SET user_score = ?, user_answer = ?, scored_at = ? WHERE id = ?",
        (user_score, user_answer, scored_at, item_id),
    )
    conn.commit()


def refresh_topic_stats(
    conn: sqlite3.Connection,
    track: str,
    topic: str,
    strategy: SchedulingStrategy | None = None,
) -> None:
    """Recompute topic_stats for `topic` from the full scored-item history.

    Deterministic and idempotent: same DB + same strategy → same output. Replays
    every score through the chosen scheduling strategy to produce interval,
    next_review, and opaque `strategy_state` JSON. Competence stays EWMA across
    all strategies (design doc §16.2 — competence and scheduling are orthogonal).

    If `strategy` is None, defaults to LeitnerEWMAStrategy (preserves pre-Phase-6
    behavior for callers that haven't been updated yet).
    """
    strategy = strategy or LeitnerEWMAStrategy()

    rows = conn.execute(
        """
        SELECT i.user_score AS score, i.scored_at AS scored_at
          FROM items i
          JOIN sessions s ON i.session_id = s.id
         WHERE s.track = ? AND i.topic = ? AND i.user_score IS NOT NULL
         ORDER BY i.scored_at ASC
        """,
        (track, topic),
    ).fetchall()
    if not rows:
        return

    scores = [r["score"] for r in rows]
    dates = [date_type.fromisoformat(r["scored_at"][:10]) for r in rows]

    # EWMA competence — same across strategies.
    competence = 0.0
    for i, s in enumerate(scores):
        competence = next_competence(competence, s, is_first=(i == 0))

    # Replay every scoring event through the strategy.
    state: dict = strategy.initial_state()
    for s, d in zip(scores, dates):
        state = strategy.update(state, s, d)
    interval = strategy.interval_days(state)

    last_seen_iso = rows[-1]["scored_at"]
    last_seen_date = dates[-1]
    next_review = next_review_date(last_seen_date, interval)

    times_seen = len(scores)
    times_correct = sum(1 for s in scores if s >= 4)

    streak = 0
    for s in reversed(scores):
        if s >= 4:
            streak += 1
        else:
            break

    conn.execute(
        """
        INSERT INTO topic_stats
            (track, topic, competence, times_seen, times_correct, last_seen,
             current_streak, next_review, review_interval, strategy_state)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(track, topic) DO UPDATE SET
            competence      = excluded.competence,
            times_seen      = excluded.times_seen,
            times_correct   = excluded.times_correct,
            last_seen       = excluded.last_seen,
            current_streak  = excluded.current_streak,
            next_review     = excluded.next_review,
            review_interval = excluded.review_interval,
            strategy_state  = excluded.strategy_state
        """,
        (
            track,
            topic,
            competence,
            times_seen,
            times_correct,
            last_seen_iso,
            streak,
            next_review.isoformat(),
            interval,
            json.dumps(state, default=str),
        ),
    )
    conn.commit()


def last_session_state(
    conn: sqlite3.Connection, track: str
) -> tuple[float, float] | None:
    """Return (difficulty, avg_score) of the most-recent COMPLETED session, or None.

    A session is "completed" only when every item has a user_score. Used by the
    difficulty-adjustment formula to compute the next session's difficulty.
    """
    row = conn.execute(
        """
        SELECT s.difficulty AS difficulty,
               AVG(i.user_score) AS avg_score,
               SUM(CASE WHEN i.user_score IS NULL THEN 1 ELSE 0 END) AS unscored
          FROM sessions s
          LEFT JOIN items i ON s.id = i.session_id
         WHERE s.track = ?
         GROUP BY s.id
         ORDER BY s.created_at DESC
         LIMIT 1
        """,
        (track,),
    ).fetchone()
    if row is None or row["avg_score"] is None or (row["unscored"] or 0) > 0:
        return None
    return float(row["difficulty"]), float(row["avg_score"])


def load_session(
    conn: sqlite3.Connection, session_id_prefix: str, track: str | None = None
) -> tuple[Session, dict] | None:
    """Look up a session by id or unique prefix. Returns (Session, meta) or None if not found.

    Raises ValueError if the prefix matches more than one session (be more specific).
    Prefers the session's `raw_json` (which preserves `mode` and `teaching_block`), then
    overlays scoring state (user_score / user_answer / scored_at) from the items table.
    """
    where = "id LIKE ?"
    params: tuple = (session_id_prefix + "%",)
    if track is not None:
        where += " AND track = ?"
        params = params + (track,)
    session_rows = conn.execute(
        f"SELECT id, track, date, created_at, difficulty, raw_json "
        f"  FROM sessions WHERE {where}",
        params,
    ).fetchall()
    if not session_rows:
        return None
    if len(session_rows) > 1:
        matches = ", ".join(r["id"][:8] for r in session_rows[:5])
        raise ValueError(
            f"Ambiguous session id {session_id_prefix!r} — matches {len(session_rows)} sessions "
            f"(e.g. {matches}). Use a longer prefix."
        )
    srow = session_rows[0]

    item_rows = conn.execute(
        "SELECT id, topic, item_type, difficulty, question, expected_answer, "
        "       user_score, user_answer, scored_at "
        "  FROM items WHERE session_id = ? ORDER BY rowid",
        (srow["id"],),
    ).fetchall()

    session: Session | None = None
    if srow["raw_json"]:
        try:
            session = Session.model_validate_json(srow["raw_json"])
        except Exception:
            session = None  # Fall through to DB-only reconstruction.

    if session is None:
        items = [
            Item(
                id=r["id"],
                topic=r["topic"],
                item_type=r["item_type"],
                difficulty=r["difficulty"],
                mode="practice",       # Best-effort default when raw_json is unavailable.
                teaching_block=None,
                question=r["question"],
                expected_answer=r["expected_answer"],
            )
            for r in item_rows
        ]
        session = Session(id=srow["id"], date=srow["date"], items=items)

    # Overlay scoring state from the DB (the raw_json snapshot never has user_score).
    by_id = {r["id"]: r for r in item_rows}
    for item in session.items:
        row = by_id.get(item.id)
        if row is None:
            continue
        item.user_score = row["user_score"]
        item.user_answer = row["user_answer"]
        item.scored_at = row["scored_at"]

    meta = {
        "track": srow["track"],
        "difficulty": float(srow["difficulty"]),
        "created_at": srow["created_at"],
        "raw_json": srow["raw_json"],
    }
    return session, meta


def list_unscored_sessions(
    conn: sqlite3.Connection, track: str, limit: int = 20
) -> list[dict]:
    """Sessions in a track that still have at least one item without a user_score."""
    rows = conn.execute(
        """
        SELECT s.id, s.date, s.created_at, s.difficulty,
               COUNT(i.id) AS item_count,
               SUM(CASE WHEN i.user_score IS NULL THEN 1 ELSE 0 END) AS unscored_count
          FROM sessions s
          LEFT JOIN items i ON s.id = i.session_id
         WHERE s.track = ?
         GROUP BY s.id
        HAVING unscored_count > 0
         ORDER BY s.created_at DESC
         LIMIT ?
        """,
        (track, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def upsert_calibration(
    conn: sqlite3.Connection, track: str, topic: str, initial_score: int
) -> None:
    """Record (or overwrite) a topic's initial calibration score."""
    calibrated_at = datetime.now().isoformat(timespec="microseconds")
    conn.execute(
        """
        INSERT INTO calibration (track, topic, initial_score, calibrated_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(track, topic) DO UPDATE SET
            initial_score = excluded.initial_score,
            calibrated_at = excluded.calibrated_at
        """,
        (track, topic, initial_score, calibrated_at),
    )
    conn.commit()


def list_topic_stats(conn: sqlite3.Connection, track: str) -> list[sqlite3.Row]:
    """Return topic_stats rows for a track, ordered by weakest topic first."""
    return conn.execute(
        "SELECT topic, competence, times_seen, times_correct, last_seen, "
        "       current_streak, next_review, review_interval "
        "  FROM topic_stats WHERE track = ? ORDER BY competence ASC, topic ASC",
        (track,),
    ).fetchall()


def list_recent_sessions(
    conn: sqlite3.Connection, track: str, limit: int = 10
) -> list[dict]:
    """Return a summary row per recent session: date, item count, average score, unscored count."""
    rows = conn.execute(
        """
        SELECT s.id, s.date, s.created_at, s.difficulty,
               COUNT(i.id) AS item_count,
               AVG(i.user_score) AS avg_score,
               SUM(CASE WHEN i.user_score IS NULL THEN 1 ELSE 0 END) AS unscored_count
          FROM sessions s
          LEFT JOIN items i ON s.id = i.session_id
         WHERE s.track = ?
         GROUP BY s.id
         ORDER BY s.created_at DESC
         LIMIT ?
        """,
        (track, limit),
    ).fetchall()
    return [dict(r) for r in rows]


def count_sessions(conn: sqlite3.Connection, track: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS n FROM sessions WHERE track = ?", (track,)
    ).fetchone()
    return int(row["n"])


def day_streak(conn: sqlite3.Connection, track: str, today: date_type | None = None) -> int:
    """Consecutive-calendar-day streak of sessions, ending today or yesterday. 0 if no sessions."""
    today = today or date_type.today()
    rows = conn.execute(
        "SELECT DISTINCT date FROM sessions WHERE track = ? ORDER BY date DESC",
        (track,),
    ).fetchall()
    if not rows:
        return 0
    dates = [date_type.fromisoformat(r["date"]) for r in rows]
    latest = dates[0]
    if latest < today - timedelta(days=1):
        return 0
    streak = 1
    prev = latest
    for d in dates[1:]:
        if (prev - d).days == 1:
            streak += 1
            prev = d
        else:
            break
    return streak
