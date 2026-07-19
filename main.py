"""Non-interactive session preview: load config + subject, generate a session, print it, save markdown.

For the interactive Phase-2+ flow (item-by-item scoring, persistence, status/history), use `orbit learn`.
"""

from __future__ import annotations

import sys

from rich.console import Console

from src.config import load_config
from src.display import display_session_preview, save_markdown_preview
from src.session import default_assignments, generate_session
from src.subject import load_subject

console = Console()


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

    assignments = default_assignments(
        subject, config.active.items_per_session, difficulty=3
    )
    session = generate_session(
        subject=subject,
        assignments=assignments,
        model=config.model,
        api_base=config.api_base,
    )

    display_session_preview(console, session, subject, config.active_track)
    path = save_markdown_preview(session, subject, config.active_track)
    console.print(f"[dim]Saved markdown preview to {path}[/dim]")
    console.print(
        "[dim]Tip: run `poetry run orbit learn` for the interactive scoring flow "
        "(persistent state, per-topic stats).[/dim]"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
