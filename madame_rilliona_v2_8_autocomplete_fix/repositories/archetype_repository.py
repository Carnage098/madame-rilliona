from __future__ import annotations

import asyncpg

from models.archetype import Archetype


SELECT_COLUMNS = """
SELECT
    a.*,
    (
        SELECT COUNT(*)
        FROM combos c
        WHERE c.archetype_id = a.id
    )::BIGINT AS combo_count,
    (
        SELECT COUNT(*)
        FROM cards cd
        WHERE LOWER(COALESCE(cd.archetype, '')) = LOWER(COALESCE(a.api_name, a.name))
    )::BIGINT AS card_count
FROM archetypes a
"""


class ArchetypeRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def create(
        self,
        *,
        name: str,
        api_name: str | None,
        presentation: str,
        play_style: str,
        difficulty: str,
        created_by: int | None,
    ) -> Archetype:
        try:
            row = await self.pool.fetchrow(
                """
                INSERT INTO archetypes (
                    name, api_name, presentation, play_style, difficulty,
                    created_by, cards_synced_at
                )
                VALUES ($1, $2, $3, $4, $5, $6, CURRENT_TIMESTAMP)
                RETURNING *
                """,
                name.strip(),
                api_name.strip() if api_name else None,
                presentation.strip(),
                play_style.strip(),
                difficulty.strip() or "Intermédiaire",
                created_by,
            )
        except asyncpg.UniqueViolationError as error:
            raise ValueError("Cet archétype existe déjà.") from error

        created = await self.get_by_id(int(row["id"]))
        if created is None:
            raise RuntimeError("L'archétype a été créé mais n'a pas pu être relu.")
        return created

    async def get_by_name(self, name: str) -> Archetype | None:
        row = await self.pool.fetchrow(
            SELECT_COLUMNS
            + """
            WHERE LOWER(a.name) = LOWER($1)
               OR LOWER(COALESCE(a.api_name, '')) = LOWER($1)
            ORDER BY CASE WHEN LOWER(a.name) = LOWER($1) THEN 0 ELSE 1 END
            LIMIT 1
            """,
            name.strip(),
        )
        return Archetype.from_record(dict(row)) if row else None

    async def get_by_id(self, archetype_id: int) -> Archetype | None:
        row = await self.pool.fetchrow(
            SELECT_COLUMNS + " WHERE a.id = $1",
            archetype_id,
        )
        return Archetype.from_record(dict(row)) if row else None

    async def list_all(self, limit: int = 100) -> list[Archetype]:
        rows = await self.pool.fetch(
            SELECT_COLUMNS + " ORDER BY a.name LIMIT $1",
            limit,
        )
        return [Archetype.from_record(dict(row)) for row in rows]

    async def autocomplete(self, query: str, limit: int = 25) -> list[Archetype]:
        normalized = query.strip()
        rows = await self.pool.fetch(
            SELECT_COLUMNS
            + """
            WHERE $1 = ''
               OR a.name ILIKE $2
               OR COALESCE(a.api_name, '') ILIKE $2
            ORDER BY a.name
            LIMIT $3
            """,
            normalized,
            f"%{normalized}%",
            limit,
        )
        return [Archetype.from_record(dict(row)) for row in rows]

    async def mark_cards_synced(
        self,
        archetype_id: int,
        *,
        api_name: str,
    ) -> Archetype | None:
        await self.pool.execute(
            """
            UPDATE archetypes
            SET api_name = $2,
                cards_synced_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $1
            """,
            archetype_id,
            api_name.strip(),
        )
        return await self.get_by_id(archetype_id)

    async def delete(self, name: str) -> bool:
        result = await self.pool.execute(
            """
            DELETE FROM archetypes
            WHERE LOWER(name) = LOWER($1)
               OR LOWER(COALESCE(api_name, '')) = LOWER($1)
            """,
            name.strip(),
        )
        return result != "DELETE 0"
