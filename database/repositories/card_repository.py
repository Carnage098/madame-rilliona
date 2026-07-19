from __future__ import annotations

import json
from collections.abc import Iterable

import asyncpg

from database import Database
from models.card import CardRecord
from utils.text import normalize_card_name


UPSERT_SQL = r"""
INSERT INTO cards (
    ygoprodeck_id,
    konami_id,
    name_en,
    name_fr,
    normalized_name_en,
    normalized_name_fr,
    description_en,
    description_fr,
    card_type_en,
    card_type_fr,
    frame_type,
    race_en,
    race_fr,
    archetype_en,
    archetype_fr,
    attribute,
    attack,
    defense,
    level,
    scale,
    link_value,
    link_markers,
    image_url,
    image_small_url,
    image_cropped_url,
    ygoprodeck_url,
    formats,
    ban_tcg,
    ban_ocg,
    ban_goat,
    raw_data_en,
    raw_data_fr,
    last_synced_at
)
VALUES (
    $1, $2, $3, $4, $5, $6, $7, $8,
    $9, $10, $11, $12, $13, $14, $15, $16,
    $17, $18, $19, $20, $21,
    $22::jsonb,
    $23, $24, $25, $26,
    $27::jsonb,
    $28, $29, $30,
    $31::jsonb,
    $32::jsonb,
    CURRENT_TIMESTAMP
)
ON CONFLICT (ygoprodeck_id) DO UPDATE SET
    konami_id = EXCLUDED.konami_id,
    name_en = EXCLUDED.name_en,
    name_fr = EXCLUDED.name_fr,
    normalized_name_en = EXCLUDED.normalized_name_en,
    normalized_name_fr = EXCLUDED.normalized_name_fr,
    description_en = EXCLUDED.description_en,
    description_fr = EXCLUDED.description_fr,
    card_type_en = EXCLUDED.card_type_en,
    card_type_fr = EXCLUDED.card_type_fr,
    frame_type = EXCLUDED.frame_type,
    race_en = EXCLUDED.race_en,
    race_fr = EXCLUDED.race_fr,
    archetype_en = EXCLUDED.archetype_en,
    archetype_fr = EXCLUDED.archetype_fr,
    attribute = EXCLUDED.attribute,
    attack = EXCLUDED.attack,
    defense = EXCLUDED.defense,
    level = EXCLUDED.level,
    scale = EXCLUDED.scale,
    link_value = EXCLUDED.link_value,
    link_markers = EXCLUDED.link_markers,
    image_url = EXCLUDED.image_url,
    image_small_url = EXCLUDED.image_small_url,
    image_cropped_url = EXCLUDED.image_cropped_url,
    ygoprodeck_url = EXCLUDED.ygoprodeck_url,
    formats = EXCLUDED.formats,
    ban_tcg = EXCLUDED.ban_tcg,
    ban_ocg = EXCLUDED.ban_ocg,
    ban_goat = EXCLUDED.ban_goat,
    raw_data_en = EXCLUDED.raw_data_en,
    raw_data_fr = EXCLUDED.raw_data_fr,
    last_synced_at = CURRENT_TIMESTAMP
"""


class CardRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    async def count(self) -> int:
        pool = self._database.require_pool()
        value = await pool.fetchval("SELECT COUNT(*) FROM cards")
        return int(value or 0)

    async def upsert(self, card: CardRecord) -> None:
        pool = self._database.require_pool()
        await pool.execute(UPSERT_SQL, *self._to_parameters(card))

    async def bulk_upsert(
        self,
        cards: Iterable[CardRecord],
        *,
        chunk_size: int = 500,
    ) -> int:
        pool = self._database.require_pool()
        chunk: list[tuple[object, ...]] = []
        processed = 0

        async with pool.acquire() as connection:
            async with connection.transaction():
                for card in cards:
                    chunk.append(self._to_parameters(card))
                    if len(chunk) >= chunk_size:
                        await connection.executemany(UPSERT_SQL, chunk)
                        processed += len(chunk)
                        chunk.clear()

                if chunk:
                    await connection.executemany(UPSERT_SQL, chunk)
                    processed += len(chunk)

        return processed

    async def get_by_id(self, card_id: int) -> CardRecord | None:
        pool = self._database.require_pool()
        row = await pool.fetchrow(
            "SELECT * FROM cards WHERE ygoprodeck_id = $1",
            card_id,
        )
        return self._from_row(row) if row else None

    async def find_best_match(self, query: str) -> CardRecord | None:
        normalized = normalize_card_name(query)
        if not normalized:
            return None

        pool = self._database.require_pool()
        row = await pool.fetchrow(
            r"""
            SELECT *
            FROM cards
            WHERE normalized_name_fr = $1
               OR normalized_name_en = $1
               OR normalized_name_fr LIKE '%' || $1 || '%'
               OR normalized_name_en LIKE '%' || $1 || '%'
            ORDER BY
                CASE
                    WHEN normalized_name_fr = $1 THEN 0
                    WHEN normalized_name_en = $1 THEN 1
                    WHEN normalized_name_fr LIKE $1 || '%' THEN 2
                    WHEN normalized_name_en LIKE $1 || '%' THEN 3
                    ELSE 4
                END,
                LENGTH(COALESCE(name_fr, name_en)),
                COALESCE(name_fr, name_en)
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
    ) -> list[CardRecord]:
        normalized = normalize_card_name(query)
        if len(normalized) < 2:
            return []

        pool = self._database.require_pool()
        rows = await pool.fetch(
            r"""
            SELECT *
            FROM cards
            WHERE normalized_name_fr LIKE '%' || $1 || '%'
               OR normalized_name_en LIKE '%' || $1 || '%'
            ORDER BY
                CASE
                    WHEN normalized_name_fr LIKE $1 || '%' THEN 0
                    WHEN normalized_name_en LIKE $1 || '%' THEN 1
                    ELSE 2
                END,
                LENGTH(COALESCE(name_fr, name_en)),
                COALESCE(name_fr, name_en)
            LIMIT $2
            """,
            normalized,
            limit,
        )
        return [self._from_row(row) for row in rows]

    async def find_by_archetype(
        self,
        archetype: str,
        *,
        limit: int = 50,
    ) -> list[CardRecord]:
        normalized = normalize_card_name(archetype)
        if not normalized:
            return []

        pool = self._database.require_pool()
        rows = await pool.fetch(
            r"""
            SELECT *
            FROM cards
            WHERE LOWER(COALESCE(archetype_fr, '')) LIKE '%' || LOWER($1) || '%'
               OR LOWER(COALESCE(archetype_en, '')) LIKE '%' || LOWER($1) || '%'
            ORDER BY COALESCE(name_fr, name_en)
            LIMIT $2
            """,
            archetype.strip(),
            limit,
        )
        return [self._from_row(row) for row in rows]

    @staticmethod
    def _to_parameters(card: CardRecord) -> tuple[object, ...]:
        return (
            card.ygoprodeck_id,
            card.konami_id,
            card.name_en,
            card.name_fr,
            card.normalized_name_en,
            card.normalized_name_fr,
            card.description_en,
            card.description_fr,
            card.card_type_en,
            card.card_type_fr,
            card.frame_type,
            card.race_en,
            card.race_fr,
            card.archetype_en,
            card.archetype_fr,
            card.attribute,
            card.attack,
            card.defense,
            card.level,
            card.scale,
            card.link_value,
            json.dumps(card.link_markers, ensure_ascii=False),
            card.image_url,
            card.image_small_url,
            card.image_cropped_url,
            card.ygoprodeck_url,
            json.dumps(card.formats, ensure_ascii=False),
            card.ban_tcg,
            card.ban_ocg,
            card.ban_goat,
            json.dumps(card.raw_data_en, ensure_ascii=False),
            json.dumps(card.raw_data_fr, ensure_ascii=False),
        )

    @staticmethod
    def _from_row(row: asyncpg.Record) -> CardRecord:
        return CardRecord(
            ygoprodeck_id=row["ygoprodeck_id"],
            konami_id=row["konami_id"],
            name_en=row["name_en"],
            name_fr=row["name_fr"],
            normalized_name_en=row["normalized_name_en"],
            normalized_name_fr=row["normalized_name_fr"],
            description_en=row["description_en"],
            description_fr=row["description_fr"],
            card_type_en=row["card_type_en"],
            card_type_fr=row["card_type_fr"],
            frame_type=row["frame_type"],
            race_en=row["race_en"],
            race_fr=row["race_fr"],
            archetype_en=row["archetype_en"],
            archetype_fr=row["archetype_fr"],
            attribute=row["attribute"],
            attack=row["attack"],
            defense=row["defense"],
            level=row["level"],
            scale=row["scale"],
            link_value=row["link_value"],
            link_markers=list(row["link_markers"] or []),
            image_url=row["image_url"],
            image_small_url=row["image_small_url"],
            image_cropped_url=row["image_cropped_url"],
            ygoprodeck_url=row["ygoprodeck_url"],
            formats=list(row["formats"] or []),
            ban_tcg=row["ban_tcg"],
            ban_ocg=row["ban_ocg"],
            ban_goat=row["ban_goat"],
            raw_data_en=dict(row["raw_data_en"] or {}),
            raw_data_fr=dict(row["raw_data_fr"] or {}),
        )

