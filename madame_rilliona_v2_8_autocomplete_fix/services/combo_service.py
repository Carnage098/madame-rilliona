from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from models.archetype import Archetype, ArchetypeRecord
from models.combo import Combo, ComboRecord
from repositories.archetype_repository import ArchetypeRepository
from repositories.combo_repository import ComboRepository


class ComboService:
    """Façade compatible entre les anciennes et nouvelles versions du bot.

    Les cogs V2.4 utilisent directement les repositories. Certaines versions
    de ``bot.py`` construisent toutefois encore un ``ComboService``. Cette
    classe conserve ce point d'entrée sans dupliquer la logique SQL.
    """

    def __init__(
        self,
        archetypes: ArchetypeRepository,
        combos: ComboRepository,
    ) -> None:
        self.archetypes = archetypes
        self.combos = combos

        # Anciens noms d'attributs conservés pour compatibilité.
        self.archetype_repository = archetypes
        self.combo_repository = combos

    async def require_archetype(self, name: str) -> ArchetypeRecord:
        archetype = await self.archetypes.get_by_name(name)
        if archetype is None:
            raise ValueError(
                "Archétype introuvable. Ajoute-le d'abord avec "
                "`/archetype ajouter`."
            )
        return archetype

    async def get_archetype(self, name: str) -> Archetype | None:
        return await self.archetypes.get_by_name(name)

    async def list_archetypes(self, limit: int = 100) -> list[Archetype]:
        return await self.archetypes.list_all(limit=limit)

    async def get_combo(self, identifier: int | str) -> ComboRecord | None:
        if isinstance(identifier, int) or str(identifier).isdigit():
            return await self.combos.get_by_id(int(identifier))
        return await self.combos.get_by_name(str(identifier))

    async def list_combos(
        self,
        archetype_name: str | None = None,
        limit: int = 100,
    ) -> list[Combo]:
        return await self.combos.list_all(
            archetype_name=archetype_name,
            limit=limit,
        )

    async def create_combo(
        self,
        *,
        archetype: str | Archetype,
        name: str,
        game_format: str = "TCG",
        banlist: str = "",
        difficulty: str = "Intermédiaire",
        line_type: str = "Standard",
        starter: str = "",
        prerequisites: str = "",
        description: str = "",
        steps: Sequence[str],
        endboard: str = "",
        interactions: str = "",
        follow_up: str = "",
        weaknesses: str = "",
        choke_points: str = "",
        recovery: str = "",
        video_url: str | None = None,
        created_by: int | None = None,
        **_: Any,
    ) -> Combo:
        entry = (
            archetype
            if isinstance(archetype, Archetype)
            else await self.require_archetype(archetype)
        )

        return await self.combos.create(
            archetype_id=entry.id,
            name=name,
            game_format=game_format,
            banlist=banlist,
            difficulty=difficulty,
            line_type=line_type,
            starter=starter,
            prerequisites=prerequisites,
            description=description,
            steps=steps,
            endboard=endboard,
            interactions=interactions,
            follow_up=follow_up,
            weaknesses=weaknesses,
            choke_points=choke_points,
            recovery=recovery,
            video_url=video_url,
            created_by=created_by,
        )

    async def delete_combo(self, identifier: int | str) -> bool:
        combo = await self.get_combo(identifier)
        if combo is None:
            return False
        return await self.combos.delete(combo.id)


__all__ = ("ComboService",)
