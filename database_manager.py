from __future__ import annotations

import asyncpg


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS cards (
    ygoprodeck_id BIGINT PRIMARY KEY,
    name_fr TEXT,
    name_en TEXT NOT NULL,
    description_fr TEXT,
    description_en TEXT,
    card_type TEXT,
    frame_type TEXT,
    card_category TEXT,
    deck_section TEXT,
    classification TEXT,
    race TEXT,
    archetype TEXT,
    attribute TEXT,
    level INTEGER,
    rank INTEGER,
    linkval INTEGER,
    atk INTEGER,
    def INTEGER,
    scale INTEGER,
    typeline TEXT[] NOT NULL DEFAULT '{}',
    link_markers TEXT[] NOT NULL DEFAULT '{}',
    ban_tcg TEXT,
    ban_ocg TEXT,
    ban_goat TEXT,
    ygoprodeck_url TEXT,
    image_url TEXT,
    image_small_url TEXT,
    import_source TEXT NOT NULL DEFAULT 'ygoprodeck',
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE cards ADD COLUMN IF NOT EXISTS frame_type TEXT;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS card_category TEXT;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS deck_section TEXT;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS classification TEXT;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS typeline TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE cards ADD COLUMN IF NOT EXISTS link_markers TEXT[] NOT NULL DEFAULT '{}';
ALTER TABLE cards ADD COLUMN IF NOT EXISTS ban_tcg TEXT;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS ban_ocg TEXT;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS ban_goat TEXT;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS ygoprodeck_url TEXT;
ALTER TABLE cards ADD COLUMN IF NOT EXISTS import_source TEXT NOT NULL DEFAULT 'ygoprodeck';
ALTER TABLE cards ADD COLUMN IF NOT EXISTS discovered_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_cards_name_fr_lower
    ON cards (LOWER(COALESCE(name_fr, '')));
CREATE INDEX IF NOT EXISTS idx_cards_name_en_lower
    ON cards (LOWER(name_en));
CREATE INDEX IF NOT EXISTS idx_cards_archetype_lower
    ON cards (LOWER(COALESCE(archetype, '')));
CREATE INDEX IF NOT EXISTS idx_cards_category_lower
    ON cards (LOWER(COALESCE(card_category, '')));
CREATE INDEX IF NOT EXISTS idx_cards_deck_section_lower
    ON cards (LOWER(COALESCE(deck_section, '')));

CREATE TABLE IF NOT EXISTS archetypes (
    id BIGSERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    api_name TEXT,
    presentation TEXT NOT NULL DEFAULT '',
    play_style TEXT NOT NULL DEFAULT '',
    difficulty TEXT NOT NULL DEFAULT 'Intermédiaire',
    created_by BIGINT,
    cards_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE archetypes ADD COLUMN IF NOT EXISTS api_name TEXT;
ALTER TABLE archetypes ADD COLUMN IF NOT EXISTS cards_synced_at TIMESTAMPTZ;

CREATE UNIQUE INDEX IF NOT EXISTS uq_archetypes_name_lower
    ON archetypes (LOWER(name));
CREATE INDEX IF NOT EXISTS idx_archetypes_api_name_lower
    ON archetypes (LOWER(COALESCE(api_name, '')));

CREATE TABLE IF NOT EXISTS combos (
    id BIGSERIAL PRIMARY KEY,
    archetype_id BIGINT NOT NULL REFERENCES archetypes(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    game_format TEXT NOT NULL DEFAULT 'TCG',
    banlist TEXT NOT NULL DEFAULT '',
    difficulty TEXT NOT NULL DEFAULT 'Intermédiaire',
    line_type TEXT NOT NULL DEFAULT 'Standard',
    starter TEXT NOT NULL DEFAULT '',
    prerequisites TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    endboard TEXT NOT NULL DEFAULT '',
    interactions TEXT NOT NULL DEFAULT '',
    follow_up TEXT NOT NULL DEFAULT '',
    weaknesses TEXT NOT NULL DEFAULT '',
    choke_points TEXT NOT NULL DEFAULT '',
    recovery TEXT NOT NULL DEFAULT '',
    video_url TEXT,
    created_by BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_combos_archetype_name_lower
    ON combos (archetype_id, LOWER(name));
CREATE INDEX IF NOT EXISTS idx_combos_archetype_id ON combos (archetype_id);

CREATE TABLE IF NOT EXISTS combo_steps (
    id BIGSERIAL PRIMARY KEY,
    combo_id BIGINT NOT NULL REFERENCES combos(id) ON DELETE CASCADE,
    step_number INTEGER NOT NULL,
    instruction TEXT NOT NULL,
    UNIQUE(combo_id, step_number)
);

CREATE TABLE IF NOT EXISTS combo_cards (
    combo_id BIGINT NOT NULL REFERENCES combos(id) ON DELETE CASCADE,
    card_id BIGINT NOT NULL REFERENCES cards(ygoprodeck_id) ON DELETE RESTRICT,
    role VARCHAR(40) NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    notes TEXT,
    PRIMARY KEY (combo_id, card_id, role)
);
"""


class Database:
    def __init__(self, database_url: str) -> None:
        self.database_url = database_url
        self.pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        if self.pool is not None:
            return
        self.pool = await asyncpg.create_pool(
            dsn=self.database_url,
            min_size=1,
            max_size=8,
            command_timeout=120,
        )

    async def initialize(self) -> None:
        pool = self.require_pool()
        async with pool.acquire() as connection:
            await connection.execute(SCHEMA_SQL)

    async def initialize_schema(self) -> None:
        await self.initialize()

    async def close(self) -> None:
        if self.pool is None:
            return
        await self.pool.close()
        self.pool = None

    def require_pool(self) -> asyncpg.Pool:
        if self.pool is None:
            raise RuntimeError("La base de données n'est pas connectée.")
        return self.pool
