"""Typer CLI: `orbit learn` (interactive), `orbit status`, `orbit history`."""

from __future__ import annotations

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
from src.persistence import (
    count_sessions,
    day_streak,
    list_recent_sessions,
    list_topic_stats,
    open_db,
    record_score,
    refresh_topic_stats,
    save_session,
)
from src.session import generate_session
from src.subject import load_subject

app = typer.Typer(add_completion=False, help="Orbit — adaptive daily learning engine.")
console = Console()


def _resolve_track(cfg: OrbitConfig, track: Optional[str]) -> str:
    name = track or cfg.active_track
    if name not in cfg.tracks:
        console.print(f"[red]Unknown track: '{name}'.[/red] "
                      f"Known: {sorted(cfg.tracks)}")
        raise typer.Exit(1)
    return name


@app.command()
def learn(
    track: Optional[str] = typer.Option(
        None, "--track", "-t", help="Track to run. Defaults to active_track in config.yaml."
    ),
) -> None:
    """Generate a new session and score it interactively, one item at a time."""
    cfg = load_config()
    track_name = _resolve_track(cfg, track)
    track_cfg = cfg.tracks[track_name]
    subject = load_subject(track_cfg.subject_file)

    with open_db(track_name) as conn:
        session_num = count_sessions(conn, track_name) + 1
        streak = day_streak(conn, track_name)

        console.print(Rule(f"Orbit — {subject.subject}"))
        header_bits = [
            f"[bold]Track:[/bold] {track_name}",
            f"[bold]Session #{session_num}[/bold]",
            f"[bold]Difficulty:[/bold] 3.0/5",  # Phase 3 makes this adaptive
        ]
        if streak > 0:
            header_bits.append(f"🔥 [bold]{streak}-day streak[/bold]")
        console.print("   ".join(header_bits))
        console.print()
        console.print(
            f"[dim]Generating a {track_cfg.items_per_session}-item session "
            f"using {cfg.model}…[/dim]"
        )

        session = generate_session(
            subject=subject,
            items_per_session=track_cfg.items_per_session,
            model=cfg.model,
            api_base=cfg.api_base,
        )
        save_session(
            conn,
            session,
            track=track_name,
            difficulty=3.0,  # Phase 3 makes this adaptive
            raw_json=session.model_dump_json(indent=2),
        )

        scores: list[int] = []
        for i, item in enumerate(session.items, 1):
            console.print()
            console.print(item_header(item, i, len(session.items)))
            tp = teach_panel(item)
            if tp:
                console.print(tp)
            console.print(question_panel(item))

            user_answer = Prompt.ask(
                "[bold]Your answer[/bold] (Enter to skip)", default="", show_default=False
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
            scores.append(score)
            console.print("[green]✓ Recorded.[/green]")

        avg = sum(scores) / len(scores) if scores else 0.0
        console.print()
        console.print(Rule("Session complete"))
        console.print(
            f"Items scored: {len(scores)}/{len(session.items)}   "
            f"Average: [bold]{avg:.2f}/5[/bold]"
        )


@app.command()
def status(
    track: Optional[str] = typer.Option(
        None, "--track", "-t", help="Track to inspect. Defaults to active_track."
    ),
) -> None:
    """Show per-topic competence, streaks, times seen for a track."""
    cfg = load_config()
    track_name = _resolve_track(cfg, track)
    subject = load_subject(cfg.tracks[track_name].subject_file)

    with open_db(track_name) as conn:
        rows = list_topic_stats(conn, track_name)
        streak = day_streak(conn, track_name)
        sessions_done = count_sessions(conn, track_name)

    console.print(Rule(f"Orbit status — {track_name}"))
    console.print(
        f"[dim]{subject.subject}[/dim]   "
        f"Sessions: [bold]{sessions_done}[/bold]   "
        f"Day streak: [bold]{streak}[/bold]"
    )

    if not rows:
        console.print()
        console.print(
            f"[dim]No topic history yet for '{track_name}'. "
            f"Run `orbit learn --track {track_name}` first.[/dim]"
        )
        return

    seen = {r["topic"] for r in rows}
    unseen = [t for t in subject.topics if t not in seen]

    table = Table(show_lines=False)
    table.add_column("Topic", style="cyan")
    table.add_column("Competence", justify="right")
    table.add_column("Seen", justify="right")
    table.add_column("Correct", justify="right")
    table.add_column("Streak", justify="right")
    table.add_column("Last seen")

    for r in rows:
        comp_value = r["competence"] or 0.0
        comp_str = f"{comp_value:.2f}/5"
        streak_val = r["current_streak"] or 0
        streak_str = (f"🔥 {streak_val}" if streak_val >= 3
                      else str(streak_val))
        table.add_row(
            r["topic"],
            comp_str,
            str(r["times_seen"]),
            str(r["times_correct"]),
            streak_str,
            r["last_seen"] or "-",
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
            f"[dim]No sessions recorded for '{track_name}'. "
            f"Run `orbit learn --track {track_name}` first.[/dim]"
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
            f"{r['difficulty']:.1f}",
        )
    console.print(table)


if __name__ == "__main__":
    app()
