from __future__ import annotations

from collections.abc import Sequence

import asyncpg

from models.combo import Combo


COMBO_SELECT = """
SELECT c.*, a.name AS archetype_name
FROM combos c
JOIN archetypes a ON a.id = c.archetype_id
"""


class ComboRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def create(
        self,
        *,
        archetype_id: int,
        name: str,
        game_format: str,
        banlist: str,
        difficulty: str,
        line_type: str,
        starter: str,
        prerequisites: str,
        description: str,
        steps: Sequence[str],
        endboard: str,
        interactions: str,
        follow_up: str,
        weaknesses: str,
        choke_points: str,
        recovery: str,
        video_url: str | None,
        created_by: int | None,
    ) -> Combo:
        cleaned_steps = [step.strip() for step in steps if step.strip()]
        if not cleaned_steps:
            raise ValueError("Le combo doit contenir au moins une étape.")

        try:
            async with self.pool.acquire() as connection:
                async with connection.transaction():
                    row = await connection.fetchrow(
                        """
                        INSERT INTO combos (
                            archetype_id, name, game_format, banlist, difficulty,
                            line_type, starter, prerequisites, description,
                            endboard, interactions, follow_up, weaknesses,
                            choke_points, recovery, video_url, created_by
                        )
                        VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9,
                            $10, $11, $12, $13, $14, $15, $16, $17
                        )
                        RETURNING *
                        """,
                        archetype_id,
                        name.strip(),
                        game_format.strip() or "TCG",
                        banlist.strip(),
                        difficulty.strip() or "Intermédiaire",
                        line_type.strip() or "Standard",
                        starter.strip(),
                        prerequisites.strip(),
                        description.strip(),
                        endboard.strip(),
                        interactions.strip(),
                        follow_up.strip(),
                        weaknesses.strip(),
                        choke_points.strip(),
                        recovery.strip(),
                        video_url.strip() if video_url else None,
                        created_by,
                    )
                    combo_id = int(row["id"])
                    await connection.executemany(
                        """
                        INSERT INTO combo_steps (combo_id, step_number, instruction)
                        VALUES ($1, $2, $3)
                        """,
                        [
                            (combo_id, number, instruction)
                            for number, instruction in enumerate(cleaned_steps, start=1)
                        ],
                    )
        except asyncpg.UniqueViolationError as error:
            raise ValueError("Un combo portant ce nom existe déjà pour cet archétype.") from error

        combo = await self.get_by_id(combo_id)
        if combo is None:
            raise RuntimeError("Le combo a été créé mais n'a pas pu être relu.")
        return combo

    async def _steps(self, combo_id: int) -> list[str]:
        rows = await self.pool.fetch(
            """
            SELECT instruction
            FROM combo_steps
            WHERE combo_id = $1
            ORDER BY step_number
            """,
            combo_id,
        )
        return [str(row["instruction"]) for row in rows]

    async def get_by_id(self, combo_id: int) -> Combo | None:
        row = await self.pool.fetchrow(
            COMBO_SELECT + " WHERE c.id = $1",
            combo_id,
        )
        if row is None:
            return None
        return Combo.from_record(dict(row), await self._steps(combo_id))

    async def get_by_name(self, name: str, archetype_name: str | None = None) -> Combo | None:
        if archetype_name:
            row = await self.pool.fetchrow(
                COMBO_SELECT
                + " WHERE LOWER(c.name) = LOWER($1) AND LOWER(a.name) = LOWER($2)",
                name.strip(),
                archetype_name.strip(),
            )
        else:
            row = await self.pool.fetchrow(
                COMBO_SELECT + " WHERE LOWER(c.name) = LOWER($1) ORDER BY c.id DESC LIMIT 1",
                name.strip(),
            )
        if row is None:
            return None
        return Combo.from_record(dict(row), await self._steps(int(row["id"])))

    async def list_all(self, archetype_name: str | None = None, limit: int = 100) -> list[Combo]:
        if archetype_name:
            rows = await self.pool.fetch(
                COMBO_SELECT
                + " WHERE LOWER(a.name) = LOWER($1) ORDER BY c.name LIMIT $2",
                archetype_name.strip(),
                limit,
            )
        else:
            rows = await self.pool.fetch(
                COMBO_SELECT + " ORDER BY a.name, c.name LIMIT $1",
                limit,
            )
        return [Combo.from_record(dict(row)) for row in rows]

    async def autocomplete(self, query: str, limit: int = 25) -> list[Combo]:
        rows = await self.pool.fetch(
            COMBO_SELECT
            + " WHERE $1 = '' OR c.name ILIKE $2 OR a.name ILIKE $2 ORDER BY c.name LIMIT $3",
            query.strip(),
            f"%{query.strip()}%",
            limit,
        )
        return [Combo.from_record(dict(row)) for row in rows]

    async def delete(self, combo_id: int) -> bool:
        result = await self.pool.execute("DELETE FROM combos WHERE id = $1", combo_id)
        return result != "DELETE 0"
