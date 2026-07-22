from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping


@dataclass(slots=True)
class Combo:
    id: int
    archetype_id: int
    archetype_name: str
    name: str
    game_format: str
    banlist: str
    difficulty: str
    line_type: str
    starter: str
    prerequisites: str
    description: str
    endboard: str
    interactions: str
    follow_up: str
    weaknesses: str
    choke_points: str
    recovery: str
    video_url: str | None
    steps: list[str] = field(default_factory=list)
    created_by: int | None = None
    created_at: datetime | None = None

    @classmethod
    def from_record(cls, row: Mapping[str, Any], steps: list[str] | None = None) -> "Combo":
        return cls(
            id=int(row["id"]),
            archetype_id=int(row["archetype_id"]),
            archetype_name=str(row.get("archetype_name") or "Archétype inconnu"),
            name=str(row["name"]),
            game_format=str(row.get("game_format") or "TCG"),
            banlist=str(row.get("banlist") or ""),
            difficulty=str(row.get("difficulty") or "Intermédiaire"),
            line_type=str(row.get("line_type") or "Standard"),
            starter=str(row.get("starter") or ""),
            prerequisites=str(row.get("prerequisites") or ""),
            description=str(row.get("description") or ""),
            endboard=str(row.get("endboard") or ""),
            interactions=str(row.get("interactions") or ""),
            follow_up=str(row.get("follow_up") or ""),
            weaknesses=str(row.get("weaknesses") or ""),
            choke_points=str(row.get("choke_points") or ""),
            recovery=str(row.get("recovery") or ""),
            video_url=row.get("video_url"),
            steps=steps or [],
            created_by=row.get("created_by"),
            created_at=row.get("created_at"),
        )


# Alias de compatibilité avec les anciennes versions du projet.
ComboRecord = Combo

__all__ = ("Combo", "ComboRecord")
