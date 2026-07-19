from __future__ import annotations

import json

import asyncpg


SCHEMA_SQL = r"""
CREATE TABLE IF NOT EXISTS cards (
    ygoprodeck_id BIGINT PRIMARY KEY,
    konami_id BIGINT,

    name_en VARCHAR(255) NOT NULL,
    name_fr VARCHAR(255),
    normalized_name_en VARCHAR(255) NOT NULL,
    normalized_name_fr VARCHAR(255),

    description_en TEXT,
    description_fr TEXT,

    card_type_en VARCHAR(100),
    card_type_fr VARCHAR(100),
    frame_type VARCHAR(50),

    race_en VARCHAR(100),
    race_fr VARCHAR(100),
    archetype_en VARCHAR(180),
    archetype_fr VARCHAR(180),
    attribute VARCHAR(20),

    attack INTEGER,
    defense INTEGER,
    level INTEGER,
    scale INTEGER,
    link_value INTEGER,
    link_markers JSONB NOT NULL DEFAULT '[]'::jsonb,

    image_url TEXT,
    image_small_url TEXT,
    image_cropped_url TEXT,
    ygoprodeck_url TEXT,

    formats JSONB NOT NULL DEFAULT '[]'::jsonb,
    ban_tcg VARCHAR(40),
    ban_ocg VARCHAR(40),
    ban_goat VARCHAR(40),

    raw_data_en JSONB NOT NULL DEFAULT '{}'::jsonb,
    raw_data_fr JSONB NOT NULL DEFAULT '{}'::jsonb,

    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_synced_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_cards_normalized_name_fr
    ON cards (normalized_name_fr);

CREATE INDEX IF NOT EXISTS idx_cards_normalized_name_en
    ON cards (normalized_name_en);

CREATE INDEX IF NOT EXISTS idx_cards_archetype_fr
    ON cards (archetype_fr);

CREATE INDEX IF NOT EXISTS idx_cards_archetype_en
    ON cards (archetype_en);

CREATE INDEX IF NOT EXISTS idx_cards_last_synced
    ON cards (last_synced_at DESC);
"""


class Database:
    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(
            dsn=self._dsn,
            min_size=1,
            max_size=10,
            command_timeout=120,
            init=self._initialize_connection,
        )

    async def initialize_schema(self) -> None:
        pool = self.require_pool()
        async with pool.acquire() as connection:
            await connection.execute(SCHEMA_SQL)

    async def close(self) -> None:
        if self.pool is not None:
            await self.pool.close()
            self.pool = None

    def require_pool(self) -> asyncpg.Pool:
        if self.pool is None:
            raise RuntimeError("La base de données n'est pas connectée.")
        return self.pool

    @staticmethod
    async def _initialize_connection(
        connection: asyncpg.Connection,
    ) -> None:
        # asyncpg renvoie autrement JSON/JSONB sous forme de chaînes.
        for pg_type in ("json", "jsonb"):
            await connection.set_type_codec(
                pg_type,
                schema="pg_catalog",
                encoder=json.dumps,
                decoder=json.loads,
                format="text",
            )
