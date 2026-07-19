from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass(slots=True)
class ComboStepRecord:
    step_number: int
    instruction: str


@dataclass(slots=True)
class ComboCreateData:
    archetype_id: int
    name: str
    normalized_name: str
    description: str
    combo_type: str
    game_format: str
    banlist: str | None
    difficulty: str
    starter_text: str
    requirements: str | None
    endboard: str
    interruptions: str | None
    follow_up: str | None
    weaknesses: str | None
    choke_points: str | None
    recovery: str | None
    video_url: str | None
    author_id: int
    status: str = "verified"


@dataclass(slots=True)
class ComboRecord:
    id: int
    archetype_id: int
    archetype_name: str

    name: str
    normalized_name: str
    description: str

    combo_type: str
    game_format: str
    banlist: str | None
    difficulty: str

    starter_text: str
    requirements: str | None
    endboard: str
    interruptions: str | None
    follow_up: str | None

    weaknesses: str | None
    choke_points: str | None
    recovery: str | None

    video_url: str | None
    author_id: int
    status: str

    created_at: datetime
    updated_at: datetime

    steps: list[ComboStepRecord] = field(default_factory=list)


@dataclass(slots=True)
class ComboSummary:
    id: int
    archetype_name: str
    name: str
    combo_type: str
    game_format: str
    difficulty: str
    starter_text: str
