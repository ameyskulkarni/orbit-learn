"""Phase 1 entry point: load config + subject, generate a session, display it, save a preview."""

from __future__ import annotations

import sys
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

from src.config import load_config
from src.models import Session, SubjectConfig
from src.session import generate_session
from src.subject import load_subject

console = Console()


def _stars(difficulty: int) -> str:
    d = max(1, min(5, int(difficulty)))
    return "★" * d + "☆" * (5 - d)


def display_session(session: Session, subject: SubjectConfig, track_name: str) -> None:
    console.print(Rule(f"Orbit — {subject.subject}"))
    console.print(
        f"[bold]Track:[/bold] {track_name}   "
        f"[bold]Date:[/bold] {session.date}   "
        f"[bold]Items:[/bold] {len(session.items)}"
    )
    console.print()

    for i, item in enumerate(session.items, 1):
        heading = (
            f"[bold cyan]{i}/{len(session.items)}[/bold cyan]  "
            f"Topic: [bold]{item.topic}[/bold]  |  "
            f"{_stars(item.difficulty)}  |  "
            f"{item.item_type}  |  {item.mode}"
        )
        console.print(Rule(heading, align="left"))
        if item.teaching_block:
            console.print(Panel(item.teaching_block, title="📖 TEACH", border_style="magenta"))
        console.print(Panel(item.question, title="📝 QUESTION", border_style="green"))
        if item.expected_answer:
            console.print(
                Panel(item.expected_answer, title="✅ EXPECTED ANSWER", border_style="dim")
            )
        console.print()


def save_markdown_preview(
    session: Session, subject: SubjectConfig, track_name: str, out_root: str | Path = "output"
) -> Path:
    """Write a plain markdown copy of the session to output/<track>/<date>.md."""
    out = Path(out_root) / track_name / f"{session.date}.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    lines: list[str] = [f"# {subject.subject} — {session.date}", ""]
    for i, item in enumerate(session.items, 1):
        lines.append(
            f"## {i}. `{item.topic}` — {item.item_type} "
            f"(difficulty {item.difficulty}/5, {item.mode})"
        )
        lines.append("")
        if item.teaching_block:
            lines.append("### Teach")
            lines.append("")
            lines.append(item.teaching_block)
            lines.append("")
        lines.append("### Question")
        lines.append("")
        lines.append(item.question)
        lines.append("")
        if item.expected_answer:
            lines.append("### Expected answer")
            lines.append("")
            lines.append(item.expected_answer)
            lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def main() -> int:
    config = load_config()
    subject = load_subject(config.active.subject_file)

    console.print(f"[dim][orbit] model    = {config.model}[/dim]")
    console.print(f"[dim][orbit] track    = {config.active_track}[/dim]")
    console.print(f"[dim][orbit] subject  = {config.active.subject_file}[/dim]")
    if config.api_base:
        console.print(f"[dim][orbit] api_base = {config.api_base}[/dim]")
    console.print(
        f"[dim]Generating a {config.active.items_per_session}-item session "
        f"for “{subject.subject}”…[/dim]"
    )
    console.print()

    session = generate_session(
        subject=subject,
        items_per_session=config.active.items_per_session,
        model=config.model,
        api_base=config.api_base,
    )

    display_session(session, subject, config.active_track)
    path = save_markdown_preview(session, subject, config.active_track)
    console.print(f"[dim]Saved markdown preview to {path}[/dim]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
