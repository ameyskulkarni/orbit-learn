"""Typer CLI: the full Orbit surface — init, calibrate, learn, status, history, run, score, dashboard, summary, export."""

from __future__ import annotations

import csv
import json
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.prompt import IntPrompt, Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from orbit_learn import __version__
from orbit_learn.config import OrbitConfig, load_config
from orbit_learn.dashboard import render_dashboard
from orbit_learn.delivery import get_delivery
from orbit_learn.display import (
    expected_panel,
    item_header,
    question_panel,
    teach_panel,
)
from orbit_learn.models import ItemAssignment, Session
from orbit_learn.persistence import (
    count_sessions,
    day_streak,
    last_session_state,
    list_recent_sessions,
    list_topic_stats,
    list_unscored_sessions,
    load_session,
    open_db,
    record_score,
    refresh_topic_stats,
    save_session,
    upsert_calibration,
)
from orbit_learn.scoring import calibration_assignments, next_difficulty, plan_session
from orbit_learn.session import generate_session
from orbit_learn.strategies import SchedulingStrategy, get_strategy
from orbit_learn.subject import load_subject


def _strategy_for(cfg: OrbitConfig, track_name: str) -> SchedulingStrategy:
    """Instantiate the scheduling strategy configured for a track."""
    return get_strategy(cfg.tracks[track_name].scoring_strategy)


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"orbit-learn {__version__}")
        raise typer.Exit()


app = typer.Typer(
    add_completion=False,
    help="Orbit — Adaptive Daily Learning Engine. Config-driven, LLM-agnostic, local-first.",
    rich_markup_mode="rich",
)
console = Console()


@app.callback()
def _root(
    version: bool = typer.Option(
        None, "--version", "-V", callback=_version_callback, is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """Root callback — hosts global options like --version."""
    _ = version  # touched so the parameter isn't 'unused'.


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
    strategy: SchedulingStrategy,
    save_calibration: bool = False,
) -> list[int]:
    """Interactive scoring loop. Skips items that already have a stored score."""
    scores: list[int] = []
    assignment_by_topic = {a.topic: a for a in assignments}
    for i, item in enumerate(session.items, 1):
        if item.user_score is not None:
            console.print(
                f"[dim]{i}/{len(session.items)} {item.topic}: already scored "
                f"({item.user_score}/5).[/dim]"
            )
            continue

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
        refresh_topic_stats(conn, track_name, item.topic, strategy=strategy)
        if save_calibration and item.topic in assignment_by_topic:
            upsert_calibration(conn, track_name, item.topic, score)
        scores.append(score)
        console.print("[green]✓ Recorded.[/green]")
    return scores


@app.command()
def init(
    check_provider: bool = typer.Option(
        True, "--check-provider/--no-check-provider",
        help="Ping the LLM provider (Ollama or hosted API) to verify the setup.",
    ),
) -> None:
    """Verify config, subject files, provider connectivity, and print a friendly next-steps card."""
    console.print(Rule("Orbit — setup check"))

    checks: list[tuple[str, bool, str]] = []
    try:
        cfg = load_config()
        checks.append(("Config loaded", True, "config.yaml"))
    except Exception as e:
        checks.append(("Config loaded", False, str(e)))
        _render_checks(checks)
        raise typer.Exit(1)

    checks.append(("Active track", True, cfg.active_track))
    checks.append(("Model", True, cfg.model))
    checks.append(("Delivery method", True, cfg.delivery.method))

    for name, tcfg in cfg.tracks.items():
        try:
            get_strategy(tcfg.scoring_strategy)
            checks.append((f"Strategy [{name}]", True, tcfg.scoring_strategy))
        except ValueError as e:
            checks.append((f"Strategy [{name}]", False, str(e)))

    for name, tcfg in cfg.tracks.items():
        p = Path(tcfg.subject_file)
        ok = p.exists()
        detail = str(p) if ok else f"MISSING: {p}"
        checks.append((f"Subject file [{name}]", ok, detail))

    for name in cfg.tracks:
        try:
            load_subject(cfg.tracks[name].subject_file)
            checks.append((f"Subject valid [{name}]", True, "parsed OK"))
        except Exception as e:
            checks.append((f"Subject valid [{name}]", False, str(e)[:80]))

    Path("data").mkdir(exist_ok=True)
    Path("output").mkdir(exist_ok=True)
    checks.append(("Data + output dirs", True, "data/, output/"))

    if check_provider:
        ok, detail = _check_provider(cfg)
        checks.append(("Provider reachable", ok, detail))

    all_ok = _render_checks(checks)

    console.print()
    if all_ok:
        active = cfg.active_track
        console.print(
            "[bold green]Setup looks good.[/bold green] "
            f"Next: [bold]orbit calibrate[/bold] "
            "to seed the adaptive engine, then [bold]orbit learn[/bold] daily."
        )
        console.print(
            f"[dim]Tip: try any of your {len(cfg.tracks)} tracks with "
            f"`orbit learn --track <name>`. Current active track: [bold]{active}[/bold].[/dim]"
        )
    else:
        console.print("[bold red]Setup has issues.[/bold red] See failures above.")
        raise typer.Exit(1)


def _render_checks(checks: list[tuple[str, bool, str]]) -> bool:
    table = Table(box=None, show_header=False, show_edge=False, padding=(0, 1))
    table.add_column(width=3)
    table.add_column("Check")
    table.add_column("Detail", style="dim")
    all_ok = True
    for name, ok, detail in checks:
        mark = Text("✓", style="green") if ok else Text("✗", style="red bold")
        table.add_row(mark, name, detail)
        all_ok &= ok
    console.print(table)
    return all_ok


def _check_provider(cfg: OrbitConfig) -> tuple[bool, str]:
    """Verify connectivity. Ollama = HTTP probe. Hosted = env-var presence check only."""
    if "/" not in cfg.model:
        # LiteLLM accepts bare model names (e.g. "gpt-4o") and auto-detects the provider,
        # but that leaves us unable to point at a specific env var. Warn rather than fail.
        return True, (
            f"model {cfg.model!r} has no 'provider/' prefix. LiteLLM will auto-detect; "
            f"ensure the matching env var (e.g. OPENAI_API_KEY) is set."
        )

    provider, tag = cfg.model.split("/", 1)

    if provider == "ollama":
        import urllib.error
        import urllib.request
        base = (cfg.api_base or "http://localhost:11434").rstrip("/")
        try:
            with urllib.request.urlopen(f"{base}/api/tags", timeout=2) as r:
                data = json.load(r)
            names = {m["name"] for m in data.get("models", [])}
            if tag in names:
                return True, f"{base} ({len(names)} models pulled, including {tag})"
            return False, (
                f"Ollama running at {base} but '{tag}' isn't pulled. "
                f"Fix: ollama pull {tag}"
            )
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            return False, f"Cannot reach Ollama at {base}. Is `ollama serve` running? ({e})"

    env_var_by_provider = {
        "anthropic": "ANTHROPIC_API_KEY",
        "openai": "OPENAI_API_KEY",
        "gemini": "GEMINI_API_KEY",
        "groq": "GROQ_API_KEY",
    }
    env_var = env_var_by_provider.get(provider)
    if env_var is None:
        return True, f"{provider}: no known env var check; assuming your setup is correct"
    if os.environ.get(env_var):
        return True, f"{provider}: {env_var} is set"
    return False, f"{provider}: {env_var} is not set. Add it to your .env or shell."


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

        scores = _run_scored_session(
            conn, session, assignments, track_name, strategy=_strategy_for(cfg, track_name)
        )

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
            conn, session, assignments, track_name,
            strategy=_strategy_for(cfg, track_name),
            save_calibration=True,
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
        f"Difficulty: [bold]{current_diff:.2f}/5[/bold]   "
        f"Strategy: [bold]{cfg.tracks[track_name].scoring_strategy}[/bold]"
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


@app.command()
def run(
    track: Optional[str] = typer.Option(
        None, "--track", "-t", help="Track to run. Defaults to active_track in config.yaml."
    ),
    method: Optional[str] = typer.Option(
        None, "--method", "-m",
        help="Override delivery.method for this run (terminal | markdown | email).",
    ),
) -> None:
    """Non-interactive: generate a session, persist it, deliver via the configured method.

    Designed for cron / GitHub Actions / any unattended schedule. Score later via
    `orbit score` (with no args to score the newest unscored session, or with a
    session-id prefix to score a specific one).
    """
    cfg = load_config()
    track_name = _resolve_track(cfg, track)
    track_cfg = cfg.tracks[track_name]
    subject = load_subject(track_cfg.subject_file)

    delivery_cfg = cfg.delivery
    if method is not None:
        # Copy the config, override just the method. Email config stays if it was there.
        delivery_cfg = cfg.delivery.model_copy(update={"method": method})
    delivery = get_delivery(delivery_cfg)

    with open_db(track_name) as conn:
        difficulty = _current_difficulty(conn, track_name)
        assignments = plan_session(
            conn,
            subject=subject,
            track=track_name,
            items_per_session=track_cfg.items_per_session,
            track_difficulty=difficulty,
        )
        streak = day_streak(conn, track_name)

        console.print(
            f"[dim][orbit run] track={track_name}  model={cfg.model}  "
            f"difficulty={difficulty:.2f}  streak={streak}  method={delivery_cfg.method}[/dim]"
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

    # Delivery lives outside the DB context — it may make external calls (SMTP, etc.).
    location = delivery.send(session, subject, track_name, streak=streak)
    console.print(
        f"[green]Delivered session {session.id[:8]}[/green]"
        + (f" → {location}" if location else "")
    )


@app.command()
def score(
    session_id: Optional[str] = typer.Argument(
        None,
        help="Session id or unique prefix. Omit to score the newest unscored session.",
    ),
    track: Optional[str] = typer.Option(
        None, "--track", "-t", help="Track to look in. Defaults to active_track."
    ),
) -> None:
    """Score a previously delivered session interactively (email / markdown workflow)."""
    cfg = load_config()
    track_name = _resolve_track(cfg, track)
    subject = load_subject(cfg.tracks[track_name].subject_file)

    with open_db(track_name) as conn:
        if session_id is None:
            unscored = list_unscored_sessions(conn, track_name, limit=5)
            if not unscored:
                console.print(
                    f"[dim]No unscored sessions in '{track_name}'. Run `orbit run` or `orbit learn` first.[/dim]"
                )
                return
            if len(unscored) > 1:
                console.print(
                    f"[yellow]Multiple unscored sessions in '{track_name}':[/yellow]"
                )
                for r in unscored:
                    console.print(
                        f"  [cyan]{r['id'][:8]}[/cyan]  {r['date']}  "
                        f"{r['unscored_count']}/{r['item_count']} unscored"
                    )
                console.print(
                    "[dim]Pass a session-id prefix to `orbit score` to pick one.[/dim]"
                )
                return
            session_id = unscored[0]["id"]

        try:
            found = load_session(conn, session_id, track=track_name)
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1)

        if found is None:
            console.print(
                f"[red]No session matching '{session_id}' in track '{track_name}'.[/red]"
            )
            raise typer.Exit(1)

        session, meta = found
        unscored_items = [i for i in session.items if i.user_score is None]
        if not unscored_items:
            console.print(
                f"[yellow]Session {session.id[:8]} is already fully scored.[/yellow]"
            )
            return

        console.print(Rule(f"Scoring session {session.id[:8]} — {session.date}"))
        console.print(
            f"[dim]Track: {track_name}   Difficulty at generation: "
            f"{meta['difficulty']:.2f}/5   Unscored: {len(unscored_items)}/{len(session.items)}[/dim]"
        )
        scored = _run_scored_session(
            conn, session, assignments=[], track_name=track_name,
            strategy=_strategy_for(cfg, track_name),
        )

        avg = sum(scored) / len(scored) if scored else 0.0
        console.print()
        console.print(Rule("Scoring complete"))
        console.print(
            f"Items scored this run: {len(scored)}   Average: [bold]{avg:.2f}/5[/bold]"
        )


@app.command()
def dashboard(
    track: Optional[str] = typer.Option(
        None, "--track", "-t", help="Track to visualize. Defaults to active_track."
    ),
) -> None:
    """Visual dashboard: competence bars, difficulty sparkline, upcoming reviews."""
    cfg = load_config()
    track_name = _resolve_track(cfg, track)
    subject = load_subject(cfg.tracks[track_name].subject_file)
    with open_db(track_name) as conn:
        render_dashboard(conn, subject=subject, track_name=track_name, console=console)


@app.command()
def summary(
    days: int = typer.Option(7, "--days", "-d", help="Digest window in days."),
) -> None:
    """Cross-track digest for the last N days (default: 7). Sessions, items, per-track highlights."""
    cfg = load_config()
    today = date.today()
    since = today - timedelta(days=days)

    console.print(Rule(f"Orbit — last {days} days"))

    grand_sessions = 0
    grand_items = 0
    grand_score_sum = 0.0
    grand_scored = 0
    per_track_rows = []

    for name in cfg.tracks:
        with open_db(name) as conn:
            row = conn.execute(
                """
                SELECT COUNT(DISTINCT s.id) AS sess,
                       COUNT(i.id) AS items,
                       SUM(i.user_score) AS score_sum,
                       SUM(CASE WHEN i.user_score IS NOT NULL THEN 1 ELSE 0 END) AS scored
                  FROM sessions s
                  LEFT JOIN items i ON s.id = i.session_id
                 WHERE s.track = ? AND s.date >= ?
                """,
                (name, since.isoformat()),
            ).fetchone()

            sess = row["sess"] or 0
            items = row["items"] or 0
            score_sum = float(row["score_sum"] or 0.0)
            scored = row["scored"] or 0
            avg = score_sum / scored if scored else None
            streak = day_streak(conn, name)

            best_row = conn.execute(
                "SELECT topic, competence FROM topic_stats WHERE track = ? "
                "ORDER BY competence DESC LIMIT 1", (name,),
            ).fetchone()
            worst_row = conn.execute(
                "SELECT topic, competence FROM topic_stats WHERE track = ? "
                "ORDER BY competence ASC LIMIT 1", (name,),
            ).fetchone()

            grand_sessions += sess
            grand_items += items
            grand_score_sum += score_sum
            grand_scored += scored

            per_track_rows.append({
                "name": name,
                "sess": sess,
                "items": items,
                "avg": avg,
                "streak": streak,
                "best": best_row,
                "worst": worst_row,
            })

    grand_avg = grand_score_sum / grand_scored if grand_scored else None
    header = (
        f"[bold]Total sessions:[/bold] {grand_sessions}   "
        f"[bold]Items scored:[/bold] {grand_scored}   "
    )
    if grand_avg is not None:
        header += f"[bold]Overall avg:[/bold] {grand_avg:.2f}/5"
    else:
        header += "[bold]Overall avg:[/bold] —"
    console.print(header)
    console.print()

    table = Table(show_header=True, header_style="bold dim")
    table.add_column("Track", style="cyan")
    table.add_column("Sessions", justify="right")
    table.add_column("Scored", justify="right")
    table.add_column("Avg", justify="right")
    table.add_column("Streak", justify="right")
    table.add_column("Strongest", style="green")
    table.add_column("Weakest", style="red")

    for r in per_track_rows:
        avg_cell = f"{r['avg']:.2f}" if r["avg"] is not None else "—"
        streak_cell = f"🔥 {r['streak']}" if r["streak"] >= 3 else str(r["streak"])
        best_cell = (
            f"{r['best']['topic']} ({r['best']['competence']:.1f})"
            if r["best"] else "—"
        )
        worst_cell = (
            f"{r['worst']['topic']} ({r['worst']['competence']:.1f})"
            if r["worst"] else "—"
        )
        table.add_row(
            r["name"],
            str(r["sess"]),
            str(r["items"]),
            avg_cell,
            streak_cell,
            best_cell,
            worst_cell,
        )
    console.print(table)


@app.command()
def export(
    fmt: str = typer.Option(
        "csv", "--format", "-f",
        help="Output format: [bold]csv[/bold] or [bold]json[/bold].",
    ),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o",
        help="Output path. Defaults to stdout for csv, to a file for json.",
    ),
    track: Optional[str] = typer.Option(
        None, "--track", "-t", help="Track to export. Defaults to active_track.",
    ),
) -> None:
    """Export all sessions + items for a track as CSV or JSON."""
    cfg = load_config()
    track_name = _resolve_track(cfg, track)

    with open_db(track_name) as conn:
        rows = conn.execute(
            """
            SELECT s.id           AS session_id,
                   s.date         AS session_date,
                   s.created_at   AS session_created_at,
                   s.difficulty   AS session_difficulty,
                   i.id           AS item_id,
                   i.topic        AS topic,
                   i.item_type    AS item_type,
                   i.difficulty   AS item_difficulty,
                   i.question     AS question,
                   i.expected_answer AS expected_answer,
                   i.user_answer  AS user_answer,
                   i.user_score   AS user_score,
                   i.scored_at    AS scored_at
              FROM sessions s
              LEFT JOIN items i ON s.id = i.session_id
             WHERE s.track = ?
             ORDER BY s.created_at ASC, i.rowid ASC
            """,
            (track_name,),
        ).fetchall()

    dicts = [dict(r) for r in rows]

    if fmt == "csv":
        import io
        buf = io.StringIO()
        if dicts:
            writer = csv.DictWriter(buf, fieldnames=list(dicts[0].keys()))
            writer.writeheader()
            writer.writerows(dicts)
        _write_or_print(output, buf.getvalue())
    elif fmt == "json":
        payload = {
            "track": track_name,
            "exported_at": datetime.now().isoformat(timespec="seconds"),
            "rows": dicts,
        }
        _write_or_print(output, json.dumps(payload, indent=2, default=str))
    else:
        console.print(f"[red]Unknown --format: {fmt!r}. Use 'csv' or 'json'.[/red]")
        raise typer.Exit(2)


def _write_or_print(output: Optional[Path], text: str) -> None:
    if output is None:
        typer.echo(text)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")
        console.print(f"[green]Wrote {output} ({len(text)} chars)[/green]")


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
