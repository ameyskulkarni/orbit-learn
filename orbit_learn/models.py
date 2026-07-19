"""Pydantic data models shared across the engine: SubjectConfig, ItemAssignment, Item, Session."""

from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field, field_validator


def _new_id() -> str:
    return uuid.uuid4().hex

ItemMode = Literal["practice", "teach_then_practice", "review"]


class SubjectConfig(BaseModel):
    """Parsed subject prompt file. This is the swappable unit — the engine reads it, the LLM uses it."""

    subject: str
    learner_context: str
    session_shape: dict[str, int]        # item_type -> count per session
    topics: list[str]
    difficulty_levels: dict[int, str]    # 1..5 -> description
    teaching_style: str
    grading_rubric: str

    @field_validator("session_shape")
    @classmethod
    def _shape_nonempty(cls, v: dict[str, int]) -> dict[str, int]:
        if not v:
            raise ValueError("SESSION_SHAPE must not be empty.")
        for name, count in v.items():
            if count < 0:
                raise ValueError(f"SESSION_SHAPE '{name}' count must be non-negative (got {count}).")
        return v

    @field_validator("topics")
    @classmethod
    def _topics_nonempty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("TOPICS must not be empty.")
        return v

    @field_validator("difficulty_levels")
    @classmethod
    def _all_five_levels(cls, v: dict[int, str]) -> dict[int, str]:
        missing = sorted(i for i in range(1, 6) if i not in v)
        if missing:
            raise ValueError(f"DIFFICULTY_LEVELS must define levels 1-5; missing: {missing}.")
        return v


class ItemAssignment(BaseModel):
    """The engine's spec for a single item: what topic, what type, at what difficulty and mode.

    Phase 1 fills these with round-robin defaults; Phase 3 uses the scoring engine.
    The LLM turns each ItemAssignment into a fully-fleshed Item.
    """

    topic: str
    item_type: str
    difficulty: int = Field(ge=1, le=5)
    mode: ItemMode = "practice"


class Item(BaseModel):
    """A single learning item as returned by the LLM, optionally annotated with scoring state."""

    id: str = Field(default_factory=_new_id)
    topic: str
    item_type: str
    difficulty: int = Field(ge=1, le=5)
    mode: ItemMode = "practice"
    teaching_block: str | None = None
    question: str
    expected_answer: str | None = None

    # Scoring state (populated when an Item is loaded from the DB; None on freshly generated items).
    user_score: int | None = None
    user_answer: str | None = None
    scored_at: str | None = None


class Session(BaseModel):
    """A full learning session: a dated list of items ready to present to the learner."""

    id: str = Field(default_factory=_new_id)
    date: str                    # ISO date (YYYY-MM-DD)
    items: list[Item]
