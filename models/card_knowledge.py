from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import unicodedata


ROLE_LABELS: dict[str, str] = {
    "starter": "Starter",
    "extender": "Extender",
    "brick": "Brick",
    "handtrap": "Handtrap",
    "board_breaker": "Board Breaker",
    "interaction": "Interaction",
    "follow_up": "Follow-up",
    "boss_monster": "Boss Monster",
    "side_card": "Carte de Side",
    "combo_piece": "Pièce de combo",
}


def role_label(role: str) -> str:
    return ROLE_LABELS.get(role, role.replace("_", " ").title())


def validate_role(role: str) -> str:
    text = unicodedata.normalize("NFKD", role.strip())
    text = "".join(character for character in text if not unicodedata.combining(character))
    normalized = text.casefold().replace("-", "_").replace(" ", "_")
    normalized = "_".join(part for part in normalized.split("_") if part)
    label_aliases = {
        "board_breaker": "board_breaker",
        "boss_monster": "boss_monster",
        "carte_de_side": "side_card",
        "side": "side_card",
        "piece_de_combo": "combo_piece",
        "piece_combo": "combo_piece",
        "followup": "follow_up",
    }
    normalized = label_aliases.get(normalized, normalized)
    if normalized not in ROLE_LABELS:
        allowed = ", ".join(ROLE_LABELS.values())
        raise ValueError(f"Rôle stratégique invalide. Valeurs autorisées : {allowed}.")
    return normalized


@dataclass(frozen=True, slots=True)
class CardAlias:
    id: int
    card_id: int
    alias: str
    normalized_alias: str
    language: str | None = None
    source: str = "staff"
    created_by: int | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class CardRole:
    card_id: int
    role: str
    notes: str | None = None
    assigned_by: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @property
    def label(self) -> str:
        return role_label(self.role)


@dataclass(frozen=True, slots=True)
class DatabaseDiagnostic:
    total_cards: int
    missing_french_effect: int
    missing_image: int
    missing_classification: int
    missing_archetype: int
    roleless_cards: int
    aliases: int
    strategic_roles: int
    pending_submissions: int
    exact_duplicate_names: int
    empty_archetypes: int
    combos_without_steps: int
    last_discovery_at: datetime | None
