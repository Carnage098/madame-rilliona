from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class ArchetypeRecord:
    id: int
    name: str
    normalized_name: str
    description: str | None
    playstyle: str | None
    difficulty: str | None
    created_by: int
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class ArchetypeSummary:
    id: int
    name: str
    playstyle: str | None
    difficulty: str | None
    combo_count: int
