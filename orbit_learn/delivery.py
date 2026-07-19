"""Pluggable delivery: how a generated session reaches the learner (terminal / markdown / email)."""

from __future__ import annotations

import html
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Protocol, runtime_checkable

from rich.console import Console

from orbit_learn.config import DeliveryConfig, EmailConfig
from orbit_learn.display import display_session_preview, save_markdown_preview
from orbit_learn.models import Session, SubjectConfig


@runtime_checkable
class Delivery(Protocol):
    """A session delivery method. Implementations return an optional locator (path, address, id)."""

    def send(
        self,
        session: Session,
        subject: SubjectConfig,
        track_name: str,
        streak: int = 0,
    ) -> str | None: ...


class TerminalDelivery:
    """Non-interactive terminal dump. For interactive scoring use `orbit learn` instead."""

    def __init__(self, console: Console | None = None) -> None:
        self.console = console or Console()

    def send(
        self,
        session: Session,
        subject: SubjectConfig,
        track_name: str,
        streak: int = 0,
    ) -> str | None:
        display_session_preview(self.console, session, subject, track_name)
        self.console.print(
            f"[dim]Score later with: orbit score {session.id[:8]}[/dim]"
        )
        return None


class MarkdownDelivery:
    """Save the session as markdown at `<out_root>/<track>/<date>.md`. Cron-friendly."""

    def __init__(self, out_root: str = "output") -> None:
        self.out_root = out_root

    def send(
        self,
        session: Session,
        subject: SubjectConfig,
        track_name: str,
        streak: int = 0,
    ) -> str | None:
        path = save_markdown_preview(session, subject, track_name, out_root=self.out_root)
        return str(path)


class EmailDelivery:
    """SMTP delivery. Password read from env var `ORBIT_EMAIL_PASSWORD`."""

    PASSWORD_ENV = "ORBIT_EMAIL_PASSWORD"

    def __init__(self, cfg: EmailConfig) -> None:
        self.cfg = cfg

    def send(
        self,
        session: Session,
        subject: SubjectConfig,
        track_name: str,
        streak: int = 0,
    ) -> str | None:
        password = os.environ.get(self.PASSWORD_ENV)
        if not password:
            raise RuntimeError(
                f"Email delivery requires the {self.PASSWORD_ENV} environment variable."
            )

        subject_line = f"Orbit — {subject.subject} — {session.date}"
        if streak > 0:
            subject_line += f" (🔥 {streak}-day streak)"

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject_line
        msg["From"] = self.cfg.from_
        msg["To"] = self.cfg.to
        msg.attach(MIMEText(_session_to_plaintext(session, subject, track_name), "plain"))
        msg.attach(MIMEText(_session_to_html(session, subject, track_name), "html"))

        with smtplib.SMTP(self.cfg.smtp_host, self.cfg.smtp_port) as smtp:
            smtp.starttls()
            smtp.login(self.cfg.from_, password)
            smtp.sendmail(self.cfg.from_, [self.cfg.to], msg.as_string())
        return f"email:{self.cfg.to}"


def get_delivery(delivery_config: DeliveryConfig) -> Delivery:
    """Instantiate the delivery method named in config.yaml."""
    method = delivery_config.method
    if method == "terminal":
        return TerminalDelivery()
    if method == "markdown":
        return MarkdownDelivery()
    if method == "email":
        if delivery_config.email is None:
            raise ValueError(
                "delivery.method is 'email' but delivery.email settings are missing in config.yaml."
            )
        return EmailDelivery(delivery_config.email)
    raise ValueError(f"Unknown delivery.method: {method!r}")


def _session_to_plaintext(session: Session, subject: SubjectConfig, track_name: str) -> str:
    lines = [
        f"{subject.subject} — {session.date}",
        f"Track: {track_name}   Items: {len(session.items)}",
        "",
    ]
    for i, item in enumerate(session.items, 1):
        lines.append(
            f"{i}. {item.topic} — {item.item_type} (difficulty {item.difficulty}/5, {item.mode})"
        )
        if item.teaching_block:
            lines += ["", "  Teach:", "  " + item.teaching_block.replace("\n", "\n  "), ""]
        lines += ["  Question:", "  " + item.question.replace("\n", "\n  "), ""]
        if item.expected_answer:
            lines += [
                "  Expected answer:",
                "  " + item.expected_answer.replace("\n", "\n  "),
                "",
            ]
    lines.append(f"Score later: orbit score {session.id[:8]}")
    return "\n".join(lines)


def _session_to_html(session: Session, subject: SubjectConfig, track_name: str) -> str:
    """Render a session as HTML for email. All interpolated content is html-escaped so LLM output
    containing angle-brackets (e.g. code samples with `<div>`) can't break the email body."""
    parts = [
        f"<h1>{html.escape(subject.subject)}</h1>",
        f"<p><strong>{html.escape(session.date)}</strong> · Track: "
        f"<code>{html.escape(track_name)}</code> · {len(session.items)} items</p>",
    ]
    for i, item in enumerate(session.items, 1):
        parts.append(
            f"<h2>{i}. <code>{html.escape(item.topic)}</code> "
            f"<small>({html.escape(item.item_type)}, difficulty {item.difficulty}/5, "
            f"{html.escape(item.mode)})</small></h2>"
        )
        if item.teaching_block:
            parts.append(
                f"<h3>Teach</h3><p>{_html_paragraphs(item.teaching_block)}</p>"
            )
        parts.append(f"<h3>Question</h3><p>{_html_paragraphs(item.question)}</p>")
        if item.expected_answer:
            parts.append(
                f"<h3>Expected answer</h3><p>{_html_paragraphs(item.expected_answer)}</p>"
            )
    parts.append(
        f"<hr><p><small>Score later with "
        f"<code>orbit score {html.escape(session.id[:8])}</code>.</small></p>"
    )
    return "\n".join(parts)


def _html_paragraphs(text: str) -> str:
    """Escape text, then convert double newlines to paragraph breaks and single newlines to <br>."""
    escaped = html.escape(text)
    return escaped.replace("\n\n", "</p><p>").replace("\n", "<br>")
