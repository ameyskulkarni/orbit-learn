"""Typer CLI: `orbit learn` (adaptive), `orbit calibrate`, `orbit status`, `orbit history`."""

from __future__ import annotations

from datetime import date
from typing import Optional

import typer
from rich.console import Console
from rich.prompt import IntPrompt, Prompt
from rich.rule import Rule
from rich.table import Table

from src.config import OrbitConfig, load_config
from src.display import (
    expected_panel,
    item_header,
    question_panel,
    teach_panel,
)
from src.models import ItemAssignment, Session
from src.persistence import (
    count_sessions,
    day_streak,
    last_session_state,
    list_recent_sessions,
    list_topic_stats,
    open_db,
    record_score,
    refresh_topic_stats,
    save_session,
    upsert_calibration,
)
from src.scoring import calibration_assignments, next_difficulty, plan_session
from src.session import generate_session
from src.subject import load_subject

app = typer.Typer(add_completion=False, help="Orbit — adaptive daily learning engine.")
console = Console()


def _resolve_track(cfg: OrbitConfig, track: Optional[str]) -> str:
    name = track or cfg.active_track
    if name not in cfg.tracks:
        console.print(
            f"[red]Unknown track: '{name}'.[/red] Known: {sorted(cfg.tracks)}"
        )
        raise typer.Exit(1)
    return name


def _current_difficulty(conn, track_name: str) -> float:
    """Compute the next session's difficulty from the last completed session, or 3.0 cold."""
    prior = last_session_state(conn, track_name)
    if prior is None:
        return 3.0
    prior_difficulty, prior_avg = prior
    return next_difficulty(prior_difficulty, prior_avg)


def _run_scored_session(
    conn,
    session: Session,
    assignments: list[ItemAssignment],
    track_name: str,
    save_calibration: bool = False,
) -> list[int]:
    """Interactive scoring loop shared by `learn` and `calibrate`."""
    scores: list[int] = []
    assignment_by_topic = {a.topic: a for a in assignments}
    for i, item in enumerate(session.items, 1):
        console.print()
        console.print(item_header(item, i, len(session.items)))
        tp = teach_panel(item)
        if tp:
            console.print(tp)
        console.print(question_panel(item))

        user_answer = Prompt.ask(
            "[bold]Your answer[/bold] (Enter to skip)",
            default="",
            show_default=False,
        )
        ep = expected_panel(item)
        if ep:
            console.print(ep)

        score = IntPrompt.ask(
            "How did you do?  "
            "[1] Blank  [2] Partial  [3] Got the idea  [4] Solid  [5] Nailed it",
            choices=["1", "2", "3", "4", "5"],
            show_choices=False,
        )
        record_score(conn, item.id, score, user_answer or None)
        refresh_topic_stats(conn, track_name, item.topic)
        if save_calibration and item.topic in assignment_by_topic:
            upsert_calibration(conn, track_name, item.topic, score)
        scores.append(score)
        console.print("[green]✓ Recorded.[/green]")
    return scores


@app.command()
def learn(
    track: Optional[str] = typer.Option(
        None, "--track", "-t", help="Track to run. Defaults to active_track in config.yaml."
    ),
) -> None:
    """Generate a new session using the adaptive engine and score it interactively."""
    cfg = load_config()
    track_name = _resolve_track(cfg, track)
    track_cfg = cfg.tracks[track_name]
    subject = load_subject(track_cfg.subject_file)

    with open_db(track_name) as conn:
        difficulty = _current_difficulty(conn, track_name)
        assignments = plan_session(
            conn,
            subject=subject,
            track=track_name,
            items_per_session=track_cfg.items_per_session,
            track_difficulty=difficulty,
        )

        session_num = count_sessions(conn, track_name) + 1
        streak = day_streak(conn, track_name)
        console.print(Rule(f"Orbit — {subject.subject}"))
        header_bits = [
            f"[bold]Track:[/bold] {track_name}",
            f"[bold]Session #{session_num}[/bold]",
            f"[bold]Difficulty:[/bold] {difficulty:.2f}/5",
        ]
        if streak > 0:
            header_bits.append(f"🔥 [bold]{streak}-day streak[/bold]")
        console.print("   ".join(header_bits))
        console.print()

        _preview_plan(assignments)
        console.print(
            f"[dim]Generating a {track_cfg.items_per_session}-item session "
            f"using {cfg.model}…[/dim]"
        )

        session = generate_session(
            subject=subject,
            assignments=assignments,
            model=cfg.model,
            api_base=cfg.api_base,
            difficulty=difficulty,
        )
        save_session(
            conn,
            session,
            track=track_name,
            difficulty=difficulty,
            raw_json=session.model_dump_json(indent=2),
        )

        scores = _run_scored_session(conn, session, assignments, track_name)

        avg = sum(scores) / len(scores) if scores else 0.0
        next_diff = next_difficulty(difficulty, avg)
        console.print()
        console.print(Rule("Session complete"))
        console.print(
            f"Items scored: {len(scores)}/{len(session.items)}   "
            f"Average: [bold]{avg:.2f}/5[/bold]   "
            f"Next difficulty: [bold]{next_diff:.2f}/5[/bold]"
        )


@app.command()
def calibrate(
    track: Optional[str] = typer.Option(
        None, "--track", "-t", help="Track to calibrate. Defaults to active_track."
    ),
    items: int = typer.Option(
        5, "--items", "-n", help="Number of calibration items (spread over difficulties 1-5)."
    ),
) -> None:
    """First-run calibration: score items at rising difficulty to seed the adaptive engine."""
    cfg = load_config()
    track_name = _resolve_track(cfg, track)
    track_cfg = cfg.tracks[track_name]
    subject = load_subject(track_cfg.subject_file)

    with open_db(track_name) as conn:
        assignments = calibration_assignments(subject, items)

        console.print(Rule(f"Orbit calibrate — {subject.subject}"))
        console.print(
            f"[dim]Scoring {items} items across topics at rising difficulties. "
            f"Your scores here seed the adaptive engine and set the starting "
            f"track difficulty.[/dim]"
        )
        console.print()
        _preview_plan(assignments)
        console.print(f"[dim]Generating with {cfg.model}…[/dim]")

        session = generate_session(
            subject=subject,
            assignments=assignments,
            model=cfg.model,
            api_base=cfg.api_base,
            difficulty=3.0,
        )
        save_session(
            conn,
            session,
            track=track_name,
            difficulty=3.0,
            raw_json=session.model_dump_json(indent=2),
        )

        scores = _run_scored_session(
            conn, session, assignments, track_name, save_calibration=True
        )

        avg = sum(scores) / len(scores) if scores else 0.0
        next_diff = next_difficulty(3.0, avg)
        console.print()
        console.print(Rule("Calibration complete"))
        console.print(
            f"Items scored: {len(scores)}/{len(session.items)}   "
            f"Average: [bold]{avg:.2f}/5[/bold]   "
            f"Starting difficulty: [bold]{next_diff:.2f}/5[/bold]"
        )
        console.print(
            f"[dim]Next `orbit learn --track {track_name}` will use this as its baseline.[/dim]"
        )


@app.command()
def status(
    track: Optional[str] = typer.Option(
        None, "--track", "-t", help="Track to inspect. Defaults to active_track."
    ),
) -> None:
    """Show per-topic competence, streaks, times seen, and next review date."""
    cfg = load_config()
    track_name = _resolve_track(cfg, track)
    subject = load_subject(cfg.tracks[track_name].subject_file)

    with open_db(track_name) as conn:
        rows = list_topic_stats(conn, track_name)
        streak = day_streak(conn, track_name)
        sessions_done = count_sessions(conn, track_name)
        current_diff = _current_difficulty(conn, track_name)

    console.print(Rule(f"Orbit status — {track_name}"))
    console.print(
        f"[dim]{subject.subject}[/dim]   "
        f"Sessions: [bold]{sessions_done}[/bold]   "
        f"Day streak: [bold]{streak}[/bold]   "
        f"Difficulty: [bold]{current_diff:.2f}/5[/bold]"
    )

    if not rows:
        console.print()
        console.print(
            f"[dim]No topic history yet for '{track_name}'. "
            f"Run `orbit calibrate --track {track_name}` or `orbit learn --track {track_name}` first.[/dim]"
        )
        return

    today = date.today()
    seen = {r["topic"] for r in rows}
    unseen = [t for t in subject.topics if t not in seen]

    table = Table(show_lines=False)
    table.add_column("Topic", style="cyan")
    table.add_column("Competence", justify="right")
    table.add_column("Seen", justify="right")
    table.add_column("Correct", justify="right")
    table.add_column("Streak", justify="right")
    table.add_column("Last seen")
    table.add_column("Next review")

    for r in rows:
        comp_value = r["competence"] or 0.0
        streak_val = r["current_streak"] or 0
        streak_str = f"🔥 {streak_val}" if streak_val >= 3 else str(streak_val)

        next_iso = r["next_review"]
        if next_iso:
            nxt = date.fromisoformat(next_iso)
            days_away = (nxt - today).days
            if days_away <= 0:
                nxt_str = f"[bold yellow]due[/bold yellow] ({next_iso})"
            elif days_away == 1:
                nxt_str = f"tomorrow ({next_iso})"
            else:
                nxt_str = f"{next_iso} (+{days_away}d)"
        else:
            nxt_str = "-"

        table.add_row(
            r["topic"],
            f"{comp_value:.2f}/5",
            str(r["times_seen"]),
            str(r["times_correct"]),
            streak_str,
            (r["last_seen"] or "-")[:10],
            nxt_str,
        )
    console.print(table)

    if unseen:
        console.print()
        console.print(
            f"[dim]{len(unseen)} topic(s) never seen: "
            f"{', '.join(unseen[:8])}{'…' if len(unseen) > 8 else ''}[/dim]"
        )


@app.command()
def history(
    track: Optional[str] = typer.Option(
        None, "--track", "-t", help="Track to inspect. Defaults to active_track."
    ),
    limit: int = typer.Option(10, "--limit", "-n", help="Number of recent sessions to show."),
) -> None:
    """Show recent sessions with their averages and difficulty."""
    cfg = load_config()
    track_name = _resolve_track(cfg, track)

    with open_db(track_name) as conn:
        rows = list_recent_sessions(conn, track_name, limit=limit)

    console.print(Rule(f"Orbit history — {track_name}"))
    if not rows:
        console.print(
            f"[dim]No sessions recorded for '{track_name}'. Run `orbit learn --track {track_name}`.[/dim]"
        )
        return

    table = Table(show_lines=False)
    table.add_column("Date", style="cyan")
    table.add_column("Started at")
    table.add_column("Items", justify="right")
    table.add_column("Avg score", justify="right")
    table.add_column("Unscored", justify="right")
    table.add_column("Difficulty", justify="right")

    for r in rows:
        avg = f"{r['avg_score']:.2f}" if r["avg_score"] is not None else "-"
        table.add_row(
            r["date"],
            r["created_at"],
            str(r["item_count"]),
            avg,
            str(r["unscored_count"]),
            f"{r['difficulty']:.2f}",
        )
    console.print(table)


def _preview_plan(assignments: list[ItemAssignment]) -> None:
    """Small Rich table showing what the scoring engine chose before we call the LLM."""
    table = Table(title="Planned items", title_style="dim", show_edge=False, show_lines=False)
    table.add_column("#", style="cyan", justify="right")
    table.add_column("Topic")
    table.add_column("Type")
    table.add_column("Difficulty", justify="right")
    table.add_column("Mode")
    for i, a in enumerate(assignments, 1):
        table.add_row(str(i), a.topic, a.item_type, f"{a.difficulty}/5", a.mode)
    console.print(table)


if __name__ == "__main__":
    app()
