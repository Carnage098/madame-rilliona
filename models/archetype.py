from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping


@dataclass(slots=True)
class Archetype:
    """Archétype enregistré dans la bibliothèque de Madame Rilliona."""

    id: int
    name: str
    presentation: str
    play_style: str
    difficulty: str
    api_name: str | None = None
    combo_count: int = 0
    card_count: int = 0
    created_by: int | None = None
    created_at: datetime | None = None
    cards_synced_at: datetime | None = None

    @property
    def catalogue_name(self) -> str:
        return self.api_name or self.name

    @classmethod
    def from_record(cls, row: Mapping[str, Any]) -> "Archetype":
        return cls(
            id=int(row["id"]),
            name=str(row["name"]),
            presentation=str(row.get("presentation") or ""),
            play_style=str(row.get("play_style") or ""),
            difficulty=str(row.get("difficulty") or "Intermédiaire"),
            api_name=row.get("api_name"),
            combo_count=int(row.get("combo_count") or 0),
            card_count=int(row.get("card_count") or 0),
            created_by=row.get("created_by"),
            created_at=row.get("created_at"),
            cards_synced_at=row.get("cards_synced_at"),
        )


ArchetypeRecord = Archetype

__all__ = ("Archetype", "ArchetypeRecord")
