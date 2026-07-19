"""Build a session prompt from a SubjectConfig, call the provider, parse the JSON reply into a Session."""

from __future__ import annotations

import json
import re
from datetime import date as date_type
from itertools import cycle, islice
from random import Random
from typing import Callable

from pydantic import ValidationError

from orbit_learn.models import Item, ItemAssignment, Session, SubjectConfig
from orbit_learn.provider import complete

MAX_RETRIES = 2  # design doc §13 Phase 1: "up to 2 retries"

# Schema shown to the LLM as a template. Formatted as an example, not JSON Schema,
# so it survives models that can't reliably follow full JSON Schema.
_SCHEMA_HINT = """{
  "session": {
    "date": "YYYY-MM-DD",
    "items": [
      {
        "topic": "<one of the topics you were assigned>",
        "item_type": "<one of the session_shape keys>",
        "difficulty": <integer 1-5>,
        "mode": "<practice | teach_then_practice | review>",
        "teaching_block": <string or null; null when mode is 'practice'>,
        "question": "<the question text shown to the learner>",
        "expected_answer": "<the reference answer used for self-scoring>"
      }
    ]
  }
}"""


def _difficulty_table(subject: SubjectConfig) -> str:
    lines = [f"  {level}: {desc}" for level, desc in sorted(subject.difficulty_levels.items())]
    return "\n".join(lines)


def build_system_prompt(subject: SubjectConfig) -> str:
    """The system prompt describes the domain, learner, and pedagogy — everything from the subject file."""
    return (
        f"You are a learning session generator for: {subject.subject}\n"
        f"Learner context: {subject.learner_context}\n"
        "\n"
        "DIFFICULTY LEVELS (integer -> what an item at that level tests):\n"
        f"{_difficulty_table(subject)}\n"
        "\n"
        "TEACHING STYLE (use this whenever the mode requires a teaching_block):\n"
        f"{subject.teaching_style}\n"
        "\n"
        "GRADING RUBRIC (calibrate your expected_answer so a self-scoring learner can apply this):\n"
        f"{subject.grading_rubric}\n"
        "\n"
        "You never pick topics; you are told which topic, type, difficulty and mode to use for each item. "
        "You only decide how to express them pedagogically. Respond in JSON only."
    )


def default_assignments(
    subject: SubjectConfig,
    items_per_session: int,
    rng: Random | None = None,
    difficulty: int = 3,
    mode: str = "practice",
) -> list[ItemAssignment]:
    """State-less selection: shuffle topics, take N, cycle item_types from SESSION_SHAPE.

    Used by `main.py` (preview mode, no persistence). The interactive `orbit learn`
    flow uses `src.scoring.plan_session` instead, which factors in per-topic history.
    """
    rng = rng or Random()
    topics = list(subject.topics)
    rng.shuffle(topics)
    chosen = topics[:items_per_session]
    types = list(subject.session_shape.keys())
    if not types:
        raise ValueError("Subject SESSION_SHAPE has no item_types.")
    type_cycle = list(islice(cycle(types), items_per_session))
    return [
        ItemAssignment(topic=t, item_type=ty, difficulty=difficulty, mode=mode)  # type: ignore[arg-type]
        for t, ty in zip(chosen, type_cycle)
    ]


def build_user_prompt(
    assignments: list[ItemAssignment],
    difficulty: float,
    today: date_type,
) -> str:
    """Compose the per-session prompt: the fixed assignments the LLM must honor + the JSON schema."""
    lines = [
        f"Generate a learning session dated {today.isoformat()}.",
        f"Overall difficulty level: {difficulty:.1f}/5",
        "",
        f"Generate exactly {len(assignments)} items, one per assignment:",
    ]
    for i, a in enumerate(assignments, 1):
        lines.append(
            f"  {i}. topic={a.topic!r} | item_type={a.item_type!r} | "
            f"difficulty={a.difficulty}/5 | mode={a.mode!r}"
        )
    lines += [
        "",
        "For each item:",
        "  - Preserve the assigned topic, item_type, difficulty, and mode exactly.",
        "  - If mode is 'teach_then_practice' or 'review', include a teaching_block per the TEACHING STYLE.",
        "  - If mode is 'practice', set teaching_block to null.",
        "  - Write a question that fits the item_type and hits the assigned difficulty level.",
        "  - Provide an expected_answer aligned with the grading rubric.",
        "",
        "Respond in JSON only, following this schema exactly:",
        _SCHEMA_HINT,
    ]
    return "\n".join(lines)


def _extract_json_object(text: str) -> str:
    """Return the first top-level {...} block from `text`, stripping code fences and prose."""
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```[a-zA-Z0-9]*\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped).strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object found in the model response.")
    return stripped[start : end + 1]


def parse_session(raw_text: str) -> Session:
    """Parse the LLM's raw text response into a validated Session. Raises on failure."""
    payload = json.loads(_extract_json_object(raw_text))
    if isinstance(payload, dict) and "session" in payload:
        payload = payload["session"]
    return Session.model_validate(payload)


def generate_session(
    subject: SubjectConfig,
    assignments: list[ItemAssignment],
    model: str,
    api_base: str | None = None,
    difficulty: float = 3.0,
    today: date_type | None = None,
    complete_fn: Callable[..., str] = complete,
) -> Session:
    """Turn a list of ItemAssignments into a full Session by prompting the LLM.

    Retries up to MAX_RETRIES times if the reply is malformed JSON or violates the
    assigned topic list. The scoring engine (or `default_assignments`) is responsible
    for picking the assignments; this function only handles the LLM round-trip.
    """
    today = today or date_type.today()
    system_prompt = build_system_prompt(subject)
    user_prompt = build_user_prompt(assignments, difficulty, today)

    last_error: Exception | None = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            raw = complete_fn(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                model=model,
                api_base=api_base,
                temperature=0.7,
                max_tokens=4000,
                response_format={"type": "json_object"},
            )
            session = parse_session(raw)
            _validate_against_assignments(session, assignments)
            return session
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            last_error = exc
            user_prompt = (
                f"Your previous response did not parse: {exc}\n"
                "Return a single JSON object, no prose, no code fences, matching:\n"
                f"{_SCHEMA_HINT}\n\n"
                f"{user_prompt}"
            )
    raise RuntimeError(
        f"LLM failed to produce a valid session JSON after {MAX_RETRIES + 1} attempts."
    ) from last_error


def _validate_against_assignments(session: Session, assignments: list[ItemAssignment]) -> None:
    """Sanity check that the LLM returned the right number of items and honored the assigned topics."""
    if len(session.items) != len(assignments):
        raise ValueError(
            f"LLM returned {len(session.items)} items but {len(assignments)} were requested."
        )
    assigned_topics = {a.topic for a in assignments}
    returned_topics = {i.topic for i in session.items}
    unknown = returned_topics - assigned_topics
    if unknown:
        raise ValueError(f"LLM returned items for topics that were not assigned: {sorted(unknown)}.")
