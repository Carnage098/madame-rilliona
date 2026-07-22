from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from models.card import Card


def _json_value(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return default
    return value


def card_to_payload(card: Card) -> dict[str, Any]:
    payload = asdict(card)
    payload["typeline"] = list(card.typeline)
    payload["link_markers"] = list(card.link_markers)
    return payload


def card_from_payload(payload: Mapping[str, Any]) -> Card:
    return Card(
        ygoprodeck_id=int(payload["ygoprodeck_id"]),
        name_en=str(payload.get("name_en") or "Carte inconnue"),
        name_fr=payload.get("name_fr"),
        description_en=payload.get("description_en"),
        description_fr=payload.get("description_fr"),
        card_type=payload.get("card_type"),
        frame_type=payload.get("frame_type"),
        card_category=payload.get("card_category"),
        deck_section=payload.get("deck_section"),
        classification=payload.get("classification"),
        race=payload.get("race"),
        archetype=payload.get("archetype"),
        attribute=payload.get("attribute"),
        level=payload.get("level"),
        rank=payload.get("rank"),
        linkval=payload.get("linkval"),
        atk=payload.get("atk"),
        defense=payload.get("defense"),
        scale=payload.get("scale"),
        typeline=tuple(str(item) for item in payload.get("typeline") or ()),
        link_markers=tuple(str(item) for item in payload.get("link_markers") or ()),
        ban_tcg=payload.get("ban_tcg"),
        ban_ocg=payload.get("ban_ocg"),
        ban_goat=payload.get("ban_goat"),
        ygoprodeck_url=payload.get("ygoprodeck_url"),
        image_url=payload.get("image_url"),
        image_small_url=payload.get("image_small_url"),
        import_source=str(payload.get("import_source") or "submission"),
    )


@dataclass(frozen=True, slots=True)
class DuplicateMatch:
    card_id: int
    display_name: str
    name_en: str
    match_type: str
    score: float

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "DuplicateMatch":
        return cls(
            card_id=int(value["card_id"]),
            display_name=str(value.get("display_name") or value.get("name_en") or "Carte inconnue"),
            name_en=str(value.get("name_en") or value.get("display_name") or "Carte inconnue"),
            match_type=str(value.get("match_type") or "similar"),
            score=float(value.get("score") or 0.0),
        )

    def to_payload(self) -> dict[str, Any]:
        return {
            "card_id": self.card_id,
            "display_name": self.display_name,
            "name_en": self.name_en,
            "match_type": self.match_type,
            "score": round(self.score, 4),
        }


@dataclass(slots=True)
class CardSubmission:
    id: int
    candidate: Card
    submitted_by: int
    guild_id: int | None
    source_type: str
    source_reference: str | None
    original_filename: str | None
    pending_image_path: Path | None
    duplicates: tuple[DuplicateMatch, ...]
    duplicate_status: str
    status: str
    review_channel_id: int | None
    review_message_id: int | None
    reviewed_by: int | None
    review_reason: str | None
    created_at: datetime | None
    reviewed_at: datetime | None
    updated_at: datetime | None

    @property
    def is_actionable(self) -> bool:
        return self.status == "pending"

    @property
    def exact_id_duplicate(self) -> DuplicateMatch | None:
        return next(
            (item for item in self.duplicates if item.match_type == "exact_id"),
            None,
        )

    @property
    def exact_name_duplicates(self) -> tuple[DuplicateMatch, ...]:
        return tuple(
            item for item in self.duplicates if item.match_type == "exact_name"
        )

    @classmethod
    def from_record(cls, row: Mapping[str, Any]) -> "CardSubmission":
        candidate_payload = _json_value(row.get("candidate_data"), {})
        duplicate_payload = _json_value(row.get("duplicate_data"), [])
        path_value = row.get("pending_image_path")
        return cls(
            id=int(row["id"]),
            candidate=card_from_payload(candidate_payload),
            submitted_by=int(row["submitted_by"]),
            guild_id=int(row["guild_id"]) if row.get("guild_id") is not None else None,
            source_type=str(row["source_type"]),
            source_reference=row.get("source_reference"),
            original_filename=row.get("original_filename"),
            pending_image_path=Path(str(path_value)) if path_value else None,
            duplicates=tuple(
                DuplicateMatch.from_mapping(item)
                for item in duplicate_payload
                if isinstance(item, Mapping)
            ),
            duplicate_status=str(row.get("duplicate_status") or "none"),
            status=str(row.get("status") or "pending"),
            review_channel_id=(
                int(row["review_channel_id"])
                if row.get("review_channel_id") is not None
                else None
            ),
            review_message_id=(
                int(row["review_message_id"])
                if row.get("review_message_id") is not None
                else None
            ),
            reviewed_by=(
                int(row["reviewed_by"])
                if row.get("reviewed_by") is not None
                else None
            ),
            review_reason=row.get("review_reason"),
            created_at=row.get("created_at"),
            reviewed_at=row.get("reviewed_at"),
            updated_at=row.get("updated_at"),
        )


__all__ = (
    "CardSubmission",
    "DuplicateMatch",
    "card_from_payload",
    "card_to_payload",
)
