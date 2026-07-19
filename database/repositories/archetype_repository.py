from __future__ import annotations

import asyncpg

from database import Database
from models.archetype import ArchetypeRecord, ArchetypeSummary
from services.errors import DuplicateArchetypeError
from utils.text import normalize_card_name


class ArchetypeRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def create(
        self,
        *,
        name: str,
        description: str | None,
        playstyle: str | None,
        difficulty: str | None,
        created_by: int,
    ) -> ArchetypeRecord:
        normalized = normalize_card_name(name)
        pool = self._database.require_pool()

        try:
            row = await pool.fetchrow(
                r"""
                INSERT INTO archetypes (
                    name,
                    normalized_name,
                    description,
                    playstyle,
                    difficulty,
                    created_by
                )
                VALUES ($1, $2, $3, $4, $5, $6)
                RETURNING *
                """,
                name.strip(),
                normalized,
                self._clean_optional(description),
                self._clean_optional(playstyle),
                self._clean_optional(difficulty),
                created_by,
            )
        except asyncpg.UniqueViolationError as exc:
            raise DuplicateArchetypeError(
                f"L'archétype « {name.strip()} » existe déjà."
            ) from exc

        if row is None:
            raise RuntimeError("Création de l'archétype impossible.")

        return self._from_row(row)

    async def get_by_id(self, archetype_id: int) -> ArchetypeRecord | None:
        pool = self._database.require_pool()
        row = await pool.fetchrow(
            "SELECT * FROM archetypes WHERE id = $1",
            archetype_id,
        )
        return self._from_row(row) if row else None

    async def find_best_match(self, query: str) -> ArchetypeRecord | None:
        normalized = normalize_card_name(query)
        if not normalized:
            return None

        pool = self._database.require_pool()
        row = await pool.fetchrow(
            r"""
            SELECT *
            FROM archetypes
            WHERE normalized_name = $1
               OR normalized_name LIKE '%' || $1 || '%'
            ORDER BY
                CASE
                    WHEN normalized_name = $1 THEN 0
                    WHEN normalized_name LIKE $1 || '%' THEN 1
                    ELSE 2
                END,
                LENGTH(name),
                name
            LIMIT 1
            """,
            normalized,
        )
        return self._from_row(row) if row else None

    async def autocomplete(
        self,
        query: str,
        *,
        limit: int = 25,
    ) -> list[ArchetypeRecord]:
        normalized = normalize_card_name(query)
        pool = self._database.require_pool()

        if normalized:
            rows = await pool.fetch(
                r"""
                SELECT *
                FROM archetypes
                WHERE normalized_name LIKE '%' || $1 || '%'
                ORDER BY
                    CASE
                        WHEN normalized_name LIKE $1 || '%' THEN 0
                        ELSE 1
                    END,
                    name
                LIMIT $2
                """,
                normalized,
                limit,
            )
        else:
            rows = await pool.fetch(
                r"""
                SELECT *
                FROM archetypes
                ORDER BY name
                LIMIT $1
                """,
                limit,
            )

        return [self._from_row(row) for row in rows]

    async def list_summaries(
        self,
        *,
        limit: int = 100,
    ) -> list[ArchetypeSummary]:
        pool = self._database.require_pool()
        rows = await pool.fetch(
            r"""
            SELECT
                a.id,
                a.name,
                a.playstyle,
                a.difficulty,
                COUNT(c.id)::INTEGER AS combo_count
            FROM archetypes AS a
            LEFT JOIN combos AS c
                ON c.archetype_id = a.id
               AND c.status = 'verified'
            GROUP BY a.id
            ORDER BY a.name
            LIMIT $1
            """,
            limit,
        )

        return [
            ArchetypeSummary(
                id=row["id"],
                name=row["name"],
                playstyle=row["playstyle"],
                difficulty=row["difficulty"],
                combo_count=row["combo_count"],
            )
            for row in rows
        ]

    async def combo_count(self, archetype_id: int) -> int:
        pool = self._database.require_pool()
        value = await pool.fetchval(
            r"""
            SELECT COUNT(*)
            FROM combos
            WHERE archetype_id = $1
              AND status = 'verified'
            """,
            archetype_id,
        )
        return int(value or 0)

    @staticmethod
    def _from_row(row: asyncpg.Record) -> ArchetypeRecord:
        return ArchetypeRecord(
            id=row["id"],
            name=row["name"],
            normalized_name=row["normalized_name"],
            description=row["description"],
            playstyle=row["playstyle"],
            difficulty=row["difficulty"],
            created_by=row["created_by"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    @staticmethod
    def _clean_optional(value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

