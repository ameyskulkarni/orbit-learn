"""Parse subject prompt files (YAML-embedded markdown) into typed SubjectConfig objects."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from orbit_learn.models import SubjectConfig

REQUIRED_FIELDS = [
    "SUBJECT",
    "LEARNER_CONTEXT",
    "SESSION_SHAPE",
    "TOPICS",
    "DIFFICULTY_LEVELS",
    "TEACHING_STYLE",
    "GRADING_RUBRIC",
]


def _normalize_session_shape(raw: Any) -> dict[str, int]:
    """SESSION_SHAPE is authored as a list of single-key mappings (one line each, so each entry
    can carry an inline comment). Flatten to a plain {item_type: count} dict."""
    if isinstance(raw, dict):
        return {str(k): int(v) for k, v in raw.items()}
    if isinstance(raw, list):
        out: dict[str, int] = {}
        for entry in raw:
            if not isinstance(entry, dict) or len(entry) != 1:
                raise ValueError(
                    f"SESSION_SHAPE entry {entry!r} must be a single 'item_type: count' mapping."
                )
            (key, value), = entry.items()
            if key in out:
                raise ValueError(f"SESSION_SHAPE item_type {key!r} appears more than once.")
            out[str(key)] = int(value)
        return out
    raise ValueError(
        f"SESSION_SHAPE must be a list of 'item_type: count' entries, got {type(raw).__name__}."
    )


def load_subject(path: str | Path) -> SubjectConfig:
    """Read a subject file from disk and return a validated SubjectConfig.

    Subject files use YAML syntax embedded in a markdown-style filename. The leading
    `# subjects/<name>.md` header is a YAML comment and is ignored.
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Subject file not found at '{p}'. Check the `subject_file` path in your config.yaml."
        )
    text = p.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise ValueError(f"Subject file '{p}' is not valid YAML: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"Subject file '{p}' must contain a YAML mapping at the top level.")

    missing = [f for f in REQUIRED_FIELDS if f not in data]
    if missing:
        raise ValueError(
            f"Subject file '{p}' is missing required fields: {missing}. "
            f"Required: {REQUIRED_FIELDS}."
        )

    return SubjectConfig(
        subject=str(data["SUBJECT"]).strip(),
        learner_context=str(data["LEARNER_CONTEXT"]).strip(),
        session_shape=_normalize_session_shape(data["SESSION_SHAPE"]),
        topics=[str(t).strip() for t in data["TOPICS"]],
        difficulty_levels={int(k): str(v).strip() for k, v in data["DIFFICULTY_LEVELS"].items()},
        teaching_style=str(data["TEACHING_STYLE"]).strip(),
        grading_rubric=str(data["GRADING_RUBRIC"]).strip(),
    )
