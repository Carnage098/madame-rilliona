from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping


@dataclass(slots=True)
class Card:
    ygoprodeck_id: int
    name_en: str
    name_fr: str | None = None
    description_en: str | None = None
    description_fr: str | None = None
    card_type: str | None = None
    race: str | None = None
    archetype: str | None = None
    attribute: str | None = None
    level: int | None = None
    rank: int | None = None
    linkval: int | None = None
    atk: int | None = None
    defense: int | None = None
    scale: int | None = None
    image_url: str | None = None
    image_small_url: str | None = None

    @property
    def display_name(self) -> str:
        return self.name_fr or self.name_en

    @property
    def display_description(self) -> str:
        return self.description_fr or self.description_en or "Aucun texte disponible."

    @classmethod
    def from_record(cls, row: Mapping[str, Any]) -> "Card":
        return cls(
            ygoprodeck_id=int(row["ygoprodeck_id"]),
            name_fr=row.get("name_fr"),
            name_en=str(row["name_en"]),
            description_fr=row.get("description_fr"),
            description_en=row.get("description_en"),
            card_type=row.get("card_type"),
            race=row.get("race"),
            archetype=row.get("archetype"),
            attribute=row.get("attribute"),
            level=row.get("level"),
            rank=row.get("rank"),
            linkval=row.get("linkval"),
            atk=row.get("atk"),
            defense=row.get("def"),
            scale=row.get("scale"),
            image_url=row.get("image_url"),
            image_small_url=row.get("image_small_url"),
        )
