from __future__ import annotations

import asyncpg

from models.archetype import Archetype


class ArchetypeRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def create(
        self,
        *,
        name: str,
        presentation: str,
        play_style: str,
        difficulty: str,
        created_by: int | None,
    ) -> Archetype:
        try:
            row = await self.pool.fetchrow(
                """
                INSERT INTO archetypes (
                    name, presentation, play_style, difficulty, created_by
                )
                VALUES ($1, $2, $3, $4, $5)
                RETURNING *, 0::BIGINT AS combo_count
                """,
                name.strip(),
                presentation.strip(),
                play_style.strip(),
                difficulty.strip() or "Intermédiaire",
                created_by,
            )
        except asyncpg.UniqueViolationError as error:
            raise ValueError("Cet archétype existe déjà.") from error
        return Archetype.from_record(dict(row))

    async def get_by_name(self, name: str) -> Archetype | None:
        row = await self.pool.fetchrow(
            """
            SELECT a.*, COUNT(c.id)::BIGINT AS combo_count
            FROM archetypes a
            LEFT JOIN combos c ON c.archetype_id = a.id
            WHERE LOWER(a.name) = LOWER($1)
            GROUP BY a.id
            """,
            name.strip(),
        )
        return Archetype.from_record(dict(row)) if row else None

    async def get_by_id(self, archetype_id: int) -> Archetype | None:
        row = await self.pool.fetchrow(
            """
            SELECT a.*, COUNT(c.id)::BIGINT AS combo_count
            FROM archetypes a
            LEFT JOIN combos c ON c.archetype_id = a.id
            WHERE a.id = $1
            GROUP BY a.id
            """,
            archetype_id,
        )
        return Archetype.from_record(dict(row)) if row else None

    async def list_all(self, limit: int = 100) -> list[Archetype]:
        rows = await self.pool.fetch(
            """
            SELECT a.*, COUNT(c.id)::BIGINT AS combo_count
            FROM archetypes a
            LEFT JOIN combos c ON c.archetype_id = a.id
            GROUP BY a.id
            ORDER BY a.name
            LIMIT $1
            """,
            limit,
        )
        return [Archetype.from_record(dict(row)) for row in rows]

    async def autocomplete(self, query: str, limit: int = 25) -> list[Archetype]:
        rows = await self.pool.fetch(
            """
            SELECT a.*, COUNT(c.id)::BIGINT AS combo_count
            FROM archetypes a
            LEFT JOIN combos c ON c.archetype_id = a.id
            WHERE $1 = '' OR a.name ILIKE $2
            GROUP BY a.id
            ORDER BY a.name
            LIMIT $3
            """,
            query.strip(),
            f"%{query.strip()}%",
            limit,
        )
        return [Archetype.from_record(dict(row)) for row in rows]

    async def delete(self, name: str) -> bool:
        result = await self.pool.execute(
            "DELETE FROM archetypes WHERE LOWER(name) = LOWER($1)",
            name.strip(),
        )
        return result != "DELETE 0"
