from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class CardRecord:
    ygoprodeck_id: int
    name_en: str
    normalized_name_en: str

    konami_id: int | None = None
    name_fr: str | None = None
    normalized_name_fr: str | None = None

    description_en: str | None = None
    description_fr: str | None = None

    card_type_en: str | None = None
    card_type_fr: str | None = None
    frame_type: str | None = None

    race_en: str | None = None
    race_fr: str | None = None
    archetype_en: str | None = None
    archetype_fr: str | None = None
    attribute: str | None = None

    attack: int | None = None
    defense: int | None = None
    level: int | None = None
    scale: int | None = None
    link_value: int | None = None
    link_markers: list[str] = field(default_factory=list)

    image_url: str | None = None
    image_small_url: str | None = None
    image_cropped_url: str | None = None
    ygoprodeck_url: str | None = None

    formats: list[str] = field(default_factory=list)
    ban_tcg: str | None = None
    ban_ocg: str | None = None
    ban_goat: str | None = None

    raw_data_en: dict[str, Any] = field(default_factory=dict)
    raw_data_fr: dict[str, Any] = field(default_factory=dict)

    @property
    def display_name(self) -> str:
        return self.name_fr or self.name_en

    @property
    def display_description(self) -> str:
        return self.description_fr or self.description_en or "Aucun texte disponible."

    @property
    def display_type(self) -> str:
        return self.card_type_fr or self.card_type_en or "Type inconnu"

    @property
    def display_race(self) -> str | None:
        return self.race_fr or self.race_en

    @property
    def display_archetype(self) -> str | None:
        return self.archetype_fr or self.archetype_en
