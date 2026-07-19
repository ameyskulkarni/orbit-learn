"""Shared Rich-based rendering (item headers, panels, markdown save) reused by CLI + delivery."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

from orbit_learn.models import Item, Session, SubjectConfig


def stars(difficulty: int) -> str:
    d = max(1, min(5, int(difficulty)))
    return "★" * d + "☆" * (5 - d)


def item_header(item: Item, index: int, total: int) -> Rule:
    heading = (
        f"[bold cyan]{index}/{total}[/bold cyan]  "
        f"Topic: [bold]{item.topic}[/bold]  |  "
        f"{stars(item.difficulty)}  |  "
        f"{item.item_type}  |  {item.mode}"
    )
    return Rule(heading, align="left")


def teach_panel(item: Item) -> Panel | None:
    if not item.teaching_block:
        return None
    return Panel(item.teaching_block, title="📖 TEACH", border_style="magenta")


def question_panel(item: Item) -> Panel:
    return Panel(item.question, title="📝 QUESTION", border_style="green")


def expected_panel(item: Item) -> Panel | None:
    if not item.expected_answer:
        return None
    return Panel(item.expected_answer, title="✅ EXPECTED ANSWER", border_style="dim")


def display_session_preview(
    console: Console, session: Session, subject: SubjectConfig, track_name: str
) -> None:
    """Non-interactive dump: header + every item's teach/question/answer at once."""
    console.print(Rule(f"Orbit — {subject.subject}"))
    console.print(
        f"[bold]Track:[/bold] {track_name}   "
        f"[bold]Date:[/bold] {session.date}   "
        f"[bold]Items:[/bold] {len(session.items)}"
    )
    console.print()

    for i, item in enumerate(session.items, 1):
        console.print(item_header(item, i, len(session.items)))
        tp = teach_panel(item)
        if tp:
            console.print(tp)
        console.print(question_panel(item))
        ep = expected_panel(item)
        if ep:
            console.print(ep)
        console.print()


def save_markdown_preview(
    session: Session,
    subject: SubjectConfig,
    track_name: str,
    out_root: str | Path = "output",
) -> Path:
    """Write a plain-markdown copy of the session to `<out_root>/<track>/<date>.md`."""
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
            lines += ["### Teach", "", item.teaching_block, ""]
        lines += ["### Question", "", item.question, ""]
        if item.expected_answer:
            lines += ["### Expected answer", "", item.expected_answer, ""]
    out.write_text("\n".join(lines), encoding="utf-8")
    return out
