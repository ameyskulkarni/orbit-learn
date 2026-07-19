"""Load and validate Orbit's `config.yaml` into typed Pydantic models."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator

DEFAULT_CONFIG_PATH = Path("config.yaml")


class TrackConfig(BaseModel):
    """Per-track settings. One entry per learning track."""

    subject_file: str
    items_per_session: int = Field(gt=0, le=20)
    scoring_strategy: Literal["ewma", "sm2", "fsrs"] = "ewma"
    enable_llm_judge: bool = False


class EmailConfig(BaseModel):
    smtp_host: str
    smtp_port: int = 587
    from_: str = Field(alias="from")
    to: str

    model_config = {"populate_by_name": True}


class DeliveryConfig(BaseModel):
    method: Literal["terminal", "markdown", "email"] = "terminal"
    email: EmailConfig | None = None


class ScheduleConfig(BaseModel):
    enabled: bool = False
    time: str = "08:00"
    method: Literal["cron", "github_actions"] = "cron"


class OrbitConfig(BaseModel):
    """The root config object."""

    model: str
    api_base: str | None = None  # Optional endpoint override (Ollama, self-hosted, LM Studio, etc.)
    active_track: str
    tracks: dict[str, TrackConfig]
    delivery: DeliveryConfig = Field(default_factory=DeliveryConfig)
    schedule: ScheduleConfig = Field(default_factory=ScheduleConfig)

    @model_validator(mode="after")
    def _active_track_must_exist(self) -> "OrbitConfig":
        if self.active_track not in self.tracks:
            known = ", ".join(sorted(self.tracks)) or "(none)"
            raise ValueError(
                f"active_track '{self.active_track}' is not defined under `tracks`. "
                f"Known tracks: {known}."
            )
        return self

    @property
    def active(self) -> TrackConfig:
        """The currently active TrackConfig."""
        return self.tracks[self.active_track]


def load_config(path: str | Path = DEFAULT_CONFIG_PATH) -> OrbitConfig:
    """Read `config.yaml` from disk and validate it. Raises with a readable message on failure."""
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Config file not found at '{config_path}'. "
            "Copy the example from the repo root and edit it to point at your model."
        )
    with config_path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    if not isinstance(raw, dict):
        raise ValueError(f"Config file '{config_path}' must contain a YAML mapping at the top level.")
    return OrbitConfig.model_validate(raw)
