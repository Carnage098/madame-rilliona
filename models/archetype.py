from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


@dataclass(slots=True)
class Archetype:
    id: int
    name: str
    presentation: str
    play_style: str
    difficulty: str
    combo_count: int = 0
    created_by: int | None = None
    created_at: datetime | None = None

    @classmethod
    def from_record(cls, row: Mapping[str, Any]) -> "Archetype":
        return cls(
            id=int(row["id"]),
            name=str(row["name"]),
            presentation=str(row.get("presentation") or ""),
            play_style=str(row.get("play_style") or ""),
            difficulty=str(row.get("difficulty") or "Intermédiaire"),
            combo_count=int(row.get("combo_count") or 0),
            created_by=row.get("created_by"),
            created_at=row.get("created_at"),
        )
