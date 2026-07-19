from __future__ import annotations

import asyncpg

from database import Database
from models.combo import (
    ComboCreateData,
    ComboRecord,
    ComboStepRecord,
    ComboSummary,
)
from services.errors import DuplicateComboError
from utils.text import normalize_card_name


COMBO_SELECT = r"""
SELECT
    c.*,
    a.name AS archetype_name
FROM combos AS c
JOIN archetypes AS a
    ON a.id = c.archetype_id
"""


class ComboRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def create(
        self,
        data: ComboCreateData,
        steps: list[str],
    ) -> ComboRecord:
        pool = self._database.require_pool()

        async with pool.acquire() as connection:
            async with connection.transaction():
                try:
                    row = await connection.fetchrow(
                        r"""
                        INSERT INTO combos (
                            archetype_id,
                            name,
                            normalized_name,
                            description,
                            combo_type,
                            game_format,
                            banlist,
                            difficulty,
                            starter_text,
                            requirements,
                            endboard,
                            interruptions,
                            follow_up,
                            weaknesses,
                            choke_points,
                            recovery,
                            video_url,
                            author_id,
                            status
                        )
                        VALUES (
                            $1, $2, $3, $4, $5, $6, $7, $8, $9,
                            $10, $11, $12, $13, $14, $15, $16,
                            $17, $18, $19
                        )
                        RETURNING id
                        """,
                        data.archetype_id,
                        data.name,
                        data.normalized_name,
                        data.description,
                        data.combo_type,
                        data.game_format,
                        data.banlist,
                        data.difficulty,
                        data.starter_text,
                        data.requirements,
                        data.endboard,
                        data.interruptions,
                        data.follow_up,
                        data.weaknesses,
                        data.choke_points,
                        data.recovery,
                        data.video_url,
                        data.author_id,
                        data.status,
                    )
                except asyncpg.UniqueViolationError as exc:
                    raise DuplicateComboError(
                        "Un combo portant ce nom existe déjà pour cet archétype."
                    ) from exc

                if row is None:
                    raise RuntimeError("Création du combo impossible.")

                combo_id = int(row["id"])

                await connection.executemany(
                    r"""
                    INSERT INTO combo_steps (
                        combo_id,
                        step_number,
                        instruction
                    )
                    VALUES ($1, $2, $3)
                    """,
                    [
                        (combo_id, index, instruction)
                        for index, instruction in enumerate(steps, start=1)
                    ],
                )

        combo = await self.get_by_id(combo_id)
        if combo is None:
            raise RuntimeError("Le combo créé n'a pas pu être relu.")
        return combo

    async def get_by_id(self, combo_id: int) -> ComboRecord | None:
        pool = self._database.require_pool()
        row = await pool.fetchrow(
            COMBO_SELECT + " WHERE c.id = $1",
            combo_id,
        )
        if row is None:
            return None

        return await self._hydrate(row)

    async def find_best_match(self, query: str) -> ComboRecord | None:
        stripped = query.strip()
        if stripped.isdigit():
            return await self.get_by_id(int(stripped))

        normalized = normalize_card_name(stripped)
        if not normalized:
            return None

        pool = self._database.require_pool()
        row = await pool.fetchrow(
            COMBO_SELECT
            + r"""
            WHERE c.status = 'verified'
              AND (
                    c.normalized_name = $1
                 OR c.normalized_name LIKE '%' || $1 || '%'
                 OR a.normalized_name LIKE '%' || $1 || '%'
              )
            ORDER BY
                CASE
                    WHEN c.normalized_name = $1 THEN 0
                    WHEN c.normalized_name LIKE $1 || '%' THEN 1
                    ELSE 2
                END,
                a.name,
                c.name
            LIMIT 1
            """,
            normalized,
        )
        return await self._hydrate(row) if row else None

    async def autocomplete(
        self,
        query: str,
        *,
        limit: int = 25,
    ) -> list[ComboSummary]:
        normalized = normalize_card_name(query)
        pool = self._database.require_pool()

        if normalized:
            rows = await pool.fetch(
                r"""
                SELECT
                    c.id,
                    a.name AS archetype_name,
                    c.name,
                    c.combo_type,
                    c.game_format,
                    c.difficulty,
                    c.starter_text
                FROM combos AS c
                JOIN archetypes AS a ON a.id = c.archetype_id
                WHERE c.status = 'verified'
                  AND (
                        c.normalized_name LIKE '%' || $1 || '%'
                     OR a.normalized_name LIKE '%' || $1 || '%'
                  )
                ORDER BY
                    CASE
                        WHEN c.normalized_name LIKE $1 || '%' THEN 0
                        WHEN a.normalized_name LIKE $1 || '%' THEN 1
                        ELSE 2
                    END,
                    a.name,
                    c.name
                LIMIT $2
                """,
                normalized,
                limit,
            )
        else:
            rows = await pool.fetch(
                r"""
                SELECT
                    c.id,
                    a.name AS archetype_name,
                    c.name,
                    c.combo_type,
                    c.game_format,
                    c.difficulty,
                    c.starter_text
                FROM combos AS c
                JOIN archetypes AS a ON a.id = c.archetype_id
                WHERE c.status = 'verified'
                ORDER BY c.created_at DESC
                LIMIT $1
                """,
                limit,
            )

        return [self._summary_from_row(row) for row in rows]

    async def list_by_archetype(
        self,
        archetype_id: int,
        *,
        limit: int = 50,
    ) -> list[ComboSummary]:
        pool = self._database.require_pool()
        rows = await pool.fetch(
            r"""
            SELECT
                c.id,
                a.name AS archetype_name,
                c.name,
                c.combo_type,
                c.game_format,
                c.difficulty,
                c.starter_text
            FROM combos AS c
            JOIN archetypes AS a ON a.id = c.archetype_id
            WHERE c.archetype_id = $1
              AND c.status = 'verified'
            ORDER BY c.name
            LIMIT $2
            """,
            archetype_id,
            limit,
        )
        return [self._summary_from_row(row) for row in rows]

    async def delete(self, combo_id: int) -> bool:
        pool = self._database.require_pool()
        result = await pool.execute(
            "DELETE FROM combos WHERE id = $1",
            combo_id,
        )
        return result == "DELETE 1"

    async def _hydrate(self, row: asyncpg.Record) -> ComboRecord:
        pool = self._database.require_pool()
        step_rows = await pool.fetch(
            r"""
            SELECT step_number, instruction
            FROM combo_steps
            WHERE combo_id = $1
            ORDER BY step_number
            """,
            row["id"],
        )

        return ComboRecord(
            id=row["id"],
            archetype_id=row["archetype_id"],
            archetype_name=row["archetype_name"],
            name=row["name"],
            normalized_name=row["normalized_name"],
            description=row["description"],
            combo_type=row["combo_type"],
            game_format=row["game_format"],
            banlist=row["banlist"],
            difficulty=row["difficulty"],
            starter_text=row["starter_text"],
            requirements=row["requirements"],
            endboard=row["endboard"],
            interruptions=row["interruptions"],
            follow_up=row["follow_up"],
            weaknesses=row["weaknesses"],
            choke_points=row["choke_points"],
            recovery=row["recovery"],
            video_url=row["video_url"],
            author_id=row["author_id"],
            status=row["status"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            steps=[
                ComboStepRecord(
                    step_number=step["step_number"],
                    instruction=step["instruction"],
                )
                for step in step_rows
            ],
        )

    @staticmethod
    def _summary_from_row(row: asyncpg.Record) -> ComboSummary:
        return ComboSummary(
            id=row["id"],
            archetype_name=row["archetype_name"],
            name=row["name"],
            combo_type=row["combo_type"],
            game_format=row["game_format"],
            difficulty=row["difficulty"],
            starter_text=row["starter_text"],
        )
