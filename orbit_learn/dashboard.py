"""Rich-based visual dashboard: competence bars, difficulty sparkline, upcoming reviews."""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from rich.console import Console, Group
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from orbit_learn.models import SubjectConfig
from orbit_learn.persistence import (
    count_sessions,
    day_streak,
    last_session_state,
    list_topic_stats,
)
from orbit_learn.scoring import next_difficulty

SPARKLINE_CHARS = "▁▂▃▄▅▆▇█"


def sparkline(values: list[float], vmin: float = 1.0, vmax: float = 5.0) -> str:
    """Render a list of floats as unicode sparkline characters."""
    if not values:
        return ""
    span = max(vmax - vmin, 1e-9)
    out = []
    for v in values:
        pos = (v - vmin) / span
        bucket = max(0, min(len(SPARKLINE_CHARS) - 1, int(pos * (len(SPARKLINE_CHARS) - 1))))
        out.append(SPARKLINE_CHARS[bucket])
    return "".join(out)


def competence_bar(competence: float, width: int = 12) -> Text:
    """A colored horizontal bar (▮▮▮▯▯▯). Red < 2, yellow 2-3, green 3-4, bright green ≥ 4."""
    filled = max(0, min(width, int(round(competence / 5.0 * width))))
    if competence < 2.0:
        style = "red"
    elif competence < 3.0:
        style = "yellow"
    elif competence < 4.0:
        style = "green"
    else:
        style = "bright_green"
    bar = "█" * filled + "░" * (width - filled)
    return Text(bar, style=style)


def _difficulty_history(conn: sqlite3.Connection, track: str, limit: int = 30) -> list[float]:
    rows = conn.execute(
        "SELECT difficulty FROM sessions WHERE track = ? "
        "ORDER BY created_at ASC LIMIT ?",
        (track, limit),
    ).fetchall()
    return [float(r["difficulty"]) for r in rows]


def _upcoming_reviews(
    conn: sqlite3.Connection, track: str, today: date, horizon_days: int = 14
) -> list[dict]:
    horizon = (today + timedelta(days=horizon_days)).isoformat()
    rows = conn.execute(
        """
        SELECT topic, next_review, review_interval, competence
          FROM topic_stats
         WHERE track = ? AND next_review IS NOT NULL AND next_review <= ?
         ORDER BY next_review ASC
         LIMIT 20
        """,
        (track, horizon),
    ).fetchall()
    return [dict(r) for r in rows]


def render_dashboard(
    conn: sqlite3.Connection,
    subject: SubjectConfig,
    track_name: str,
    console: Console | None = None,
) -> None:
    """Print the full dashboard for a track."""
    console = console or Console()
    today = date.today()

    sessions_done = count_sessions(conn, track_name)
    streak = day_streak(conn, track_name)
    prior = last_session_state(conn, track_name)
    current_difficulty = next_difficulty(prior[0], prior[1]) if prior else 3.0

    # --- Header ---
    header = Text.assemble(
        ("Orbit — ", "bold"),
        (subject.subject, "bold cyan"),
        "\n",
        (f"Track: ", "dim"),
        (f"{track_name}   ", ""),
        (f"Sessions: ", "dim"),
        (f"{sessions_done}   ", "bold"),
        (f"Difficulty: ", "dim"),
        (f"{current_difficulty:.2f}/5   ", "bold"),
    )
    if streak > 0:
        header.append("🔥 ", "yellow")
        header.append(f"{streak}-day streak", "bold yellow")

    # --- Difficulty sparkline ---
    diffs = _difficulty_history(conn, track_name)
    if diffs:
        spark = sparkline(diffs)
        diff_panel = Panel(
            Text.assemble(
                (spark, "bold cyan"),
                f"   {diffs[0]:.1f} → {diffs[-1]:.1f}   ",
                (f"({len(diffs)} sessions)", "dim"),
            ),
            title="Difficulty over time",
            border_style="dim",
        )
    else:
        diff_panel = Panel(
            Text("No sessions yet.", style="dim"),
            title="Difficulty over time",
            border_style="dim",
        )

    # --- Topic competence bars ---
    stats = list_topic_stats(conn, track_name)
    seen = {r["topic"] for r in stats}
    unseen = [t for t in subject.topics if t not in seen]

    topic_table = Table(box=None, show_header=True, header_style="bold dim")
    topic_table.add_column("Topic", style="cyan")
    topic_table.add_column("Competence", no_wrap=True)
    topic_table.add_column("Score", justify="right")
    topic_table.add_column("Seen", justify="right")
    topic_table.add_column("Streak", justify="right")

    if stats:
        for r in stats:
            comp = float(r["competence"] or 0.0)
            streak_val = int(r["current_streak"] or 0)
            streak_cell = (
                Text(f"🔥 {streak_val}", style="yellow") if streak_val >= 3
                else Text(str(streak_val), style="dim")
            )
            topic_table.add_row(
                r["topic"],
                competence_bar(comp),
                f"{comp:.2f}/5",
                str(r["times_seen"]),
                streak_cell,
            )
    else:
        topic_table.add_row(
            Text("(no topics scored yet)", style="dim"), Text(""), "", "", ""
        )

    unseen_line = ""
    if unseen:
        preview = ", ".join(unseen[:5])
        more = f" (+{len(unseen) - 5} more)" if len(unseen) > 5 else ""
        unseen_line = f"[dim]Never seen: {preview}{more}[/dim]"

    topic_group = Group(topic_table, Text.from_markup(unseen_line) if unseen else Text(""))
    topic_panel = Panel(topic_group, title="Topic competence", border_style="dim")

    # --- Upcoming reviews ---
    reviews = _upcoming_reviews(conn, track_name, today)
    review_table = Table(box=None, show_header=True, header_style="bold dim")
    review_table.add_column("When", style="cyan")
    review_table.add_column("Topic")
    review_table.add_column("Competence", justify="right")
    review_table.add_column("Interval", justify="right")

    if reviews:
        for r in reviews:
            nxt = date.fromisoformat(r["next_review"])
            days_away = (nxt - today).days
            if days_away <= 0:
                when_cell = Text("due today", style="bold yellow")
            elif days_away == 1:
                when_cell = Text("tomorrow", style="yellow")
            else:
                when_cell = Text(f"{r['next_review']} (+{days_away}d)", style="")
            review_table.add_row(
                when_cell,
                r["topic"],
                f"{float(r['competence'] or 0.0):.2f}/5",
                f"{float(r['review_interval'] or 1.0):.0f}d",
            )
    else:
        review_table.add_row(Text("(no upcoming reviews)", style="dim"), "", "", "")

    review_panel = Panel(review_table, title="Upcoming reviews (14d)", border_style="dim")

    # --- Print everything ---
    console.print(Rule("Orbit dashboard"))
    console.print(header)
    console.print()
    console.print(diff_panel)
    console.print(topic_panel)
    console.print(review_panel)
