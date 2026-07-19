from __future__ import annotations

import re
from urllib.parse import urlparse

from models.archetype import ArchetypeRecord
from models.combo import ComboCreateData, ComboRecord
from repositories.archetype_repository import ArchetypeRepository
from repositories.combo_repository import ComboRepository
from services.errors import (
    ArchetypeNotFoundError,
    ComboNotFoundError,
    InvalidComboError,
)
from utils.text import normalize_card_name


_STEP_PREFIX_RE = re.compile(
    r"^\s*(?:(?:étape|step)\s*)?\d+\s*[\.\)\-:]\s*|^\s*[-•]\s*",
    flags=re.IGNORECASE,
)

_SECTION_RE = re.compile(
    r"(?im)^\s*(faiblesses?|choke\s*points?|points?\s*de\s*rupture|"
    r"recovery|récupération|reprise)\s*:\s*"
)


class ComboService:
    def __init__(
        self,
        *,
        archetypes: ArchetypeRepository,
        combos: ComboRepository,
    ) -> None:
        self._archetypes = archetypes
        self._combos = combos

    async def create_combo(
        self,
        *,
        archetype_query: str,
        name: str,
        description: str,
        combo_type: str,
        game_format: str,
        banlist: str | None,
        difficulty: str,
        starter_text: str,
        requirements: str | None,
        steps_text: str,
        endboard: str,
        interruptions: str | None,
        follow_up: str | None,
        analysis_text: str | None,
        video_url: str | None,
        author_id: int,
    ) -> ComboRecord:
        archetype = await self._archetypes.find_best_match(archetype_query)
        if archetype is None:
            raise ArchetypeNotFoundError(
                "L'archétype indiqué n'existe pas dans Madame Rilliona."
            )

        clean_name = name.strip()
        clean_description = description.strip()
        clean_starter = starter_text.strip()
        clean_endboard = endboard.strip()

        if len(clean_name) < 3:
            raise InvalidComboError(
                "Le nom du combo doit contenir au moins 3 caractères."
            )
        if len(clean_description) < 10:
            raise InvalidComboError(
                "La description doit contenir au moins 10 caractères."
            )
        if not clean_starter:
            raise InvalidComboError("Les cartes de départ sont obligatoires.")
        if not clean_endboard:
            raise InvalidComboError("Le terrain final est obligatoire.")

        steps = self.parse_steps(steps_text)
        weaknesses, choke_points, recovery = self.parse_analysis(
            analysis_text
        )

        clean_video_url = self.validate_video_url(video_url)

        data = ComboCreateData(
            archetype_id=archetype.id,
            name=clean_name,
            normalized_name=normalize_card_name(clean_name),
            description=clean_description,
            combo_type=combo_type,
            game_format=game_format,
            banlist=self.clean_optional(banlist),
            difficulty=difficulty,
            starter_text=clean_starter,
            requirements=self.clean_optional(requirements),
            endboard=clean_endboard,
            interruptions=self.clean_optional(interruptions),
            follow_up=self.clean_optional(follow_up),
            weaknesses=weaknesses,
            choke_points=choke_points,
            recovery=recovery,
            video_url=clean_video_url,
            author_id=author_id,
        )

        return await self._combos.create(data, steps)

    async def get_combo(self, query: str) -> ComboRecord:
        combo = await self._combos.find_best_match(query)
        if combo is None:
            raise ComboNotFoundError("Combo introuvable.")
        return combo

    async def delete_combo(self, combo_id: int) -> None:
        deleted = await self._combos.delete(combo_id)
        if not deleted:
            raise ComboNotFoundError("Ce combo n'existe plus.")

    @staticmethod
    def parse_steps(value: str) -> list[str]:
        lines = []
        for raw_line in value.splitlines():
            cleaned = _STEP_PREFIX_RE.sub("", raw_line).strip()
            if cleaned:
                lines.append(cleaned)

        if len(lines) < 2:
            raise InvalidComboError(
                "Le combo doit contenir au moins deux étapes, "
                "avec une étape par ligne."
            )
        if len(lines) > 50:
            raise InvalidComboError(
                "Un combo ne peut pas dépasser 50 étapes."
            )
        if any(len(line) > 1000 for line in lines):
            raise InvalidComboError(
                "Une étape dépasse la limite de 1 000 caractères."
            )

        return lines

    @staticmethod
    def parse_analysis(
        value: str | None,
    ) -> tuple[str | None, str | None, str | None]:
        cleaned = ComboService.clean_optional(value)
        if cleaned is None:
            return None, None, None

        matches = list(_SECTION_RE.finditer(cleaned))
        if not matches:
            return cleaned, None, None

        sections: dict[str, list[str]] = {
            "weaknesses": [],
            "choke_points": [],
            "recovery": [],
        }

        for index, match in enumerate(matches):
            heading = match.group(1).casefold()
            start = match.end()
            end = (
                matches[index + 1].start()
                if index + 1 < len(matches)
                else len(cleaned)
            )
            content = cleaned[start:end].strip()

            if not content:
                continue

            if "choke" in heading or "rupture" in heading:
                sections["choke_points"].append(content)
            elif "recovery" in heading or "récup" in heading or "reprise" in heading:
                sections["recovery"].append(content)
            else:
                sections["weaknesses"].append(content)

        return (
            "\n\n".join(sections["weaknesses"]) or None,
            "\n\n".join(sections["choke_points"]) or None,
            "\n\n".join(sections["recovery"]) or None,
        )

    @staticmethod
    def validate_video_url(value: str | None) -> str | None:
        cleaned = ComboService.clean_optional(value)
        if cleaned is None:
            return None

        parsed = urlparse(cleaned)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise InvalidComboError(
                "Le lien vidéo doit être une adresse HTTP ou HTTPS valide."
            )

        return cleaned

    @staticmethod
    def clean_optional(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

