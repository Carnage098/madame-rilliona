from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import asyncpg

from models.card import Card


UPSERT_SQL = """
INSERT INTO cards (
    ygoprodeck_id, name_fr, name_en, description_fr, description_en,
    card_type, race, archetype, attribute, level, rank, linkval,
    atk, def, scale, image_url, image_small_url, updated_at
)
VALUES (
    $1, $2, $3, $4, $5, $6, $7, $8, $9,
    $10, $11, $12, $13, $14, $15, $16, $17, CURRENT_TIMESTAMP
)
ON CONFLICT (ygoprodeck_id) DO UPDATE SET
    name_fr = EXCLUDED.name_fr,
    name_en = EXCLUDED.name_en,
    description_fr = EXCLUDED.description_fr,
    description_en = EXCLUDED.description_en,
    card_type = EXCLUDED.card_type,
    race = EXCLUDED.race,
    archetype = EXCLUDED.archetype,
    attribute = EXCLUDED.attribute,
    level = EXCLUDED.level,
    rank = EXCLUDED.rank,
    linkval = EXCLUDED.linkval,
    atk = EXCLUDED.atk,
    def = EXCLUDED.def,
    scale = EXCLUDED.scale,
    image_url = EXCLUDED.image_url,
    image_small_url = EXCLUDED.image_small_url,
    updated_at = CURRENT_TIMESTAMP
"""


class CardRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    @staticmethod
    def _parameters(card: Card) -> tuple[Any, ...]:
        return (
            card.ygoprodeck_id,
            card.name_fr,
            card.name_en,
            card.description_fr,
            card.description_en,
            card.card_type,
            card.race,
            card.archetype,
            card.attribute,
            card.level,
            card.rank,
            card.linkval,
            card.atk,
            card.defense,
            card.scale,
            card.image_url,
            card.image_small_url,
        )

    async def upsert_many(self, cards: Iterable[Card], batch_size: int = 500) -> int:
        values = [self._parameters(card) for card in cards]
        if not values:
            return 0

        async with self.pool.acquire() as connection:
            async with connection.transaction():
                for index in range(0, len(values), batch_size):
                    await connection.executemany(UPSERT_SQL, values[index:index + batch_size])
        return len(values)

    async def search(self, query: str, limit: int = 10) -> list[Card]:
        normalized = query.strip()
        rows = await self.pool.fetch(
            """
            SELECT *
            FROM cards
            WHERE COALESCE(name_fr, '') ILIKE $1
               OR name_en ILIKE $1
            ORDER BY
                CASE
                    WHEN LOWER(COALESCE(name_fr, name_en)) = LOWER($2) THEN 0
                    WHEN LOWER(COALESCE(name_fr, name_en)) LIKE LOWER($2) || '%' THEN 1
                    ELSE 2
                END,
                COALESCE(name_fr, name_en)
            LIMIT $3
            """,
            f"%{normalized}%",
            normalized,
            limit,
        )
        return [Card.from_record(dict(row)) for row in rows]

    async def autocomplete(self, query: str, limit: int = 25) -> list[Card]:
        if not query.strip():
            rows = await self.pool.fetch(
                "SELECT * FROM cards ORDER BY COALESCE(name_fr, name_en) LIMIT $1",
                limit,
            )
        else:
            rows = await self.pool.fetch(
                """
                SELECT * FROM cards
                WHERE COALESCE(name_fr, '') ILIKE $1 OR name_en ILIKE $1
                ORDER BY COALESCE(name_fr, name_en)
                LIMIT $2
                """,
                f"%{query.strip()}%",
                limit,
            )
        return [Card.from_record(dict(row)) for row in rows]

    async def get_by_id(self, card_id: int) -> Card | None:
        row = await self.pool.fetchrow(
            "SELECT * FROM cards WHERE ygoprodeck_id = $1",
            card_id,
        )
        return Card.from_record(dict(row)) if row else None

    async def list_by_archetype(self, archetype: str, limit: int = 50) -> list[Card]:
        rows = await self.pool.fetch(
            """
            SELECT * FROM cards
            WHERE archetype ILIKE $1
            ORDER BY COALESCE(name_fr, name_en)
            LIMIT $2
            """,
            f"%{archetype.strip()}%",
            limit,
        )
        return [Card.from_record(dict(row)) for row in rows]

    async def count(self) -> int:
        return int(await self.pool.fetchval("SELECT COUNT(*) FROM cards") or 0)
