from __future__ import annotations

from typing import Any
import unicodedata

import asyncpg

from models.card import Card
from models.card_knowledge import CardAlias, CardRole, DatabaseDiagnostic, validate_role


class CardKnowledgeRepository:
    """Alias, rôles stratégiques, filtres et diagnostic du catalogue."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    @staticmethod
    def _normalize_alias(value: str) -> str:
        text = unicodedata.normalize("NFKD", value or "")
        text = "".join(character for character in text if not unicodedata.combining(character))
        return "".join(character for character in text.casefold() if character.isalnum())

    async def add_alias(
        self,
        *,
        card_id: int,
        alias: str,
        created_by: int | None,
        language: str | None = None,
        source: str = "staff",
    ) -> CardAlias:
        cleaned = " ".join(alias.strip().split())
        normalized = self._normalize_alias(cleaned)
        if len(normalized) < 2:
            raise ValueError("L'alias doit contenir au moins deux caractères utiles.")

        async with self.pool.acquire() as connection:
            async with connection.transaction():
                exists = await connection.fetchval(
                    "SELECT EXISTS(SELECT 1 FROM cards WHERE ygoprodeck_id = $1)",
                    card_id,
                )
                if not exists:
                    raise ValueError("Cette carte n'existe pas dans le catalogue local.")

                name_rows = await connection.fetch(
                    "SELECT ygoprodeck_id, name_fr, name_en FROM cards"
                )
                for name_row in name_rows:
                    existing_id = int(name_row["ygoprodeck_id"])
                    official_names = (name_row["name_fr"], name_row["name_en"])
                    if not any(
                        self._normalize_alias(str(name)) == normalized
                        for name in official_names
                        if name
                    ):
                        continue
                    if existing_id == card_id:
                        raise ValueError(
                            "Cet alias correspond déjà au nom officiel de cette carte."
                        )
                    display_name = name_row["name_fr"] or name_row["name_en"]
                    raise ValueError(
                        f"Cet alias correspond au nom officiel de **{display_name}**."
                    )

                conflict = await connection.fetchrow(
                    """
                    SELECT ca.*, COALESCE(c.name_fr, c.name_en) AS card_name
                    FROM card_aliases ca
                    JOIN cards c ON c.ygoprodeck_id = ca.card_id
                    WHERE ca.normalized_alias = $1
                    """,
                    normalized,
                )
                if conflict and int(conflict["card_id"]) != card_id:
                    raise ValueError(
                        f"Cet alias est déjà associé à **{conflict['card_name']}**."
                    )

                row = await connection.fetchrow(
                    """
                    INSERT INTO card_aliases (
                        card_id, alias, normalized_alias, language, source, created_by
                    )
                    VALUES ($1, $2, $3, $4, $5, $6)
                    ON CONFLICT (normalized_alias) DO UPDATE SET
                        alias = EXCLUDED.alias,
                        language = COALESCE(EXCLUDED.language, card_aliases.language),
                        source = EXCLUDED.source,
                        created_by = EXCLUDED.created_by
                    RETURNING *
                    """,
                    card_id,
                    cleaned,
                    normalized,
                    language.strip()[:20] if language and language.strip() else None,
                    source.strip()[:30] or "staff",
                    created_by,
                )
        return CardAlias(**dict(row))

    async def remove_alias(self, *, card_id: int, alias: str) -> bool:
        normalized = self._normalize_alias(alias)
        result = await self.pool.execute(
            "DELETE FROM card_aliases WHERE card_id = $1 AND normalized_alias = $2",
            card_id,
            normalized,
        )
        return result.endswith("1")

    async def list_aliases(self, card_id: int) -> list[CardAlias]:
        rows = await self.pool.fetch(
            """
            SELECT * FROM card_aliases
            WHERE card_id = $1
            ORDER BY alias
            """,
            card_id,
        )
        return [CardAlias(**dict(row)) for row in rows]

    async def find_card_by_alias(self, query: str) -> Card | None:
        normalized = self._normalize_alias(query)
        if not normalized:
            return None
        row = await self.pool.fetchrow(
            """
            SELECT c.*
            FROM card_aliases ca
            JOIN cards c ON c.ygoprodeck_id = ca.card_id
            WHERE ca.normalized_alias = $1
            LIMIT 1
            """,
            normalized,
        )
        return Card.from_record(dict(row)) if row else None

    async def autocomplete_aliases(
        self,
        query: str,
        *,
        limit: int = 25,
    ) -> list[tuple[Card, str]]:
        normalized = self._normalize_alias(query)
        if not normalized:
            return []
        rows = await self.pool.fetch(
            """
            SELECT c.*, ca.alias AS matched_alias
            FROM card_aliases ca
            JOIN cards c ON c.ygoprodeck_id = ca.card_id
            WHERE ca.normalized_alias LIKE $1
            ORDER BY
                CASE WHEN ca.normalized_alias = $2 THEN 0 ELSE 1 END,
                LENGTH(ca.normalized_alias), ca.alias
            LIMIT $3
            """,
            f"%{normalized}%",
            normalized,
            limit,
        )
        return [
            (Card.from_record(dict(row)), str(row["matched_alias"]))
            for row in rows
        ]

    async def set_role(
        self,
        *,
        card_id: int,
        role: str,
        notes: str | None,
        assigned_by: int | None,
    ) -> CardRole:
        normalized_role = validate_role(role)
        exists = await self.pool.fetchval(
            "SELECT EXISTS(SELECT 1 FROM cards WHERE ygoprodeck_id = $1)",
            card_id,
        )
        if not exists:
            raise ValueError("Cette carte n'existe pas dans le catalogue local.")

        row = await self.pool.fetchrow(
            """
            INSERT INTO card_roles (card_id, role, notes, assigned_by)
            VALUES ($1, $2, $3, $4)
            ON CONFLICT (card_id, role) DO UPDATE SET
                notes = EXCLUDED.notes,
                assigned_by = EXCLUDED.assigned_by,
                updated_at = CURRENT_TIMESTAMP
            RETURNING *
            """,
            card_id,
            normalized_role,
            notes.strip()[:1000] if notes and notes.strip() else None,
            assigned_by,
        )
        return CardRole(**dict(row))

    async def remove_role(self, *, card_id: int, role: str) -> bool:
        normalized_role = validate_role(role)
        result = await self.pool.execute(
            "DELETE FROM card_roles WHERE card_id = $1 AND role = $2",
            card_id,
            normalized_role,
        )
        return result.endswith("1")

    async def list_roles(self, card_id: int) -> list[CardRole]:
        rows = await self.pool.fetch(
            """
            SELECT * FROM card_roles
            WHERE card_id = $1
            ORDER BY role
            """,
            card_id,
        )
        return [CardRole(**dict(row)) for row in rows]

    async def roles_for_cards(
        self,
        card_ids: list[int] | tuple[int, ...],
    ) -> dict[int, list[CardRole]]:
        if not card_ids:
            return {}
        rows = await self.pool.fetch(
            """
            SELECT * FROM card_roles
            WHERE card_id = ANY($1::BIGINT[])
            ORDER BY card_id, role
            """,
            list(dict.fromkeys(int(card_id) for card_id in card_ids)),
        )
        result: dict[int, list[CardRole]] = {}
        for row in rows:
            item = CardRole(**dict(row))
            result.setdefault(item.card_id, []).append(item)
        return result

    async def role_counts_by_archetype(self, archetype: str) -> dict[str, int]:
        rows = await self.pool.fetch(
            """
            SELECT cr.role, COUNT(DISTINCT cr.card_id) AS total
            FROM card_roles cr
            JOIN cards c ON c.ygoprodeck_id = cr.card_id
            WHERE LOWER(COALESCE(c.archetype, '')) = LOWER($1)
               OR c.archetype ILIKE $2
            GROUP BY cr.role
            ORDER BY total DESC, cr.role
            """,
            archetype.strip(),
            f"%{archetype.strip()}%",
        )
        return {str(row["role"]): int(row["total"]) for row in rows}

    async def cards_by_archetype_role(
        self,
        archetype: str,
        role: str,
        *,
        limit: int = 25,
    ) -> list[Card]:
        normalized_role = validate_role(role)
        rows = await self.pool.fetch(
            """
            SELECT c.*
            FROM cards c
            JOIN card_roles cr ON cr.card_id = c.ygoprodeck_id
            WHERE cr.role = $1
              AND (
                LOWER(COALESCE(c.archetype, '')) = LOWER($2)
                OR c.archetype ILIKE $3
              )
            ORDER BY COALESCE(c.name_fr, c.name_en)
            LIMIT $4
            """,
            normalized_role,
            archetype.strip(),
            f"%{archetype.strip()}%",
            limit,
        )
        return [Card.from_record(dict(row)) for row in rows]

    async def archetype_breakdown(self, archetype: str) -> dict[str, dict[str, int]]:
        category_rows = await self.pool.fetch(
            """
            SELECT COALESCE(card_category, 'Non classée') AS label, COUNT(*) AS total
            FROM cards
            WHERE LOWER(COALESCE(archetype, '')) = LOWER($1)
               OR archetype ILIKE $2
            GROUP BY COALESCE(card_category, 'Non classée')
            ORDER BY total DESC, label
            """,
            archetype.strip(),
            f"%{archetype.strip()}%",
        )
        section_rows = await self.pool.fetch(
            """
            SELECT COALESCE(deck_section, 'Section inconnue') AS label, COUNT(*) AS total
            FROM cards
            WHERE LOWER(COALESCE(archetype, '')) = LOWER($1)
               OR archetype ILIKE $2
            GROUP BY COALESCE(deck_section, 'Section inconnue')
            ORDER BY total DESC, label
            """,
            archetype.strip(),
            f"%{archetype.strip()}%",
        )
        return {
            "categories": {
                str(row["label"]): int(row["total"]) for row in category_rows
            },
            "sections": {
                str(row["label"]): int(row["total"]) for row in section_rows
            },
            "roles": await self.role_counts_by_archetype(archetype),
        }

    async def advanced_search(
        self,
        *,
        archetype: str | None = None,
        category: str | None = None,
        deck_section: str | None = None,
        attribute: str | None = None,
        race: str | None = None,
        effect_text: str | None = None,
        role: str | None = None,
        min_atk: int | None = None,
        max_atk: int | None = None,
        level: int | None = None,
        rank: int | None = None,
        linkval: int | None = None,
        limit: int = 10,
    ) -> list[Card]:
        clauses: list[str] = []
        values: list[Any] = []

        def add(clause: str, value: Any) -> None:
            values.append(value)
            clauses.append(clause.replace("$?", f"${len(values)}"))

        if archetype and archetype.strip():
            add("c.archetype ILIKE $?", f"%{archetype.strip()}%")
        if category and category.strip():
            add("LOWER(COALESCE(c.card_category, '')) = LOWER($?)", category.strip())
        if deck_section and deck_section.strip():
            add("LOWER(COALESCE(c.deck_section, '')) = LOWER($?)", deck_section.strip())
        if attribute and attribute.strip():
            add("LOWER(COALESCE(c.attribute, '')) = LOWER($?)", attribute.strip())
        if race and race.strip():
            add("LOWER(COALESCE(c.race, '')) = LOWER($?)", race.strip())
        if effect_text and effect_text.strip():
            values.append(f"%{effect_text.strip()}%")
            position = len(values)
            clauses.append(
                f"(COALESCE(c.description_fr, '') ILIKE ${position} "
                f"OR COALESCE(c.description_en, '') ILIKE ${position})"
            )
        if role:
            normalized_role = validate_role(role)
            add(
                "EXISTS (SELECT 1 FROM card_roles cr WHERE cr.card_id = c.ygoprodeck_id AND cr.role = $?)",
                normalized_role,
            )
        if min_atk is not None:
            add("c.atk >= $?", int(min_atk))
        if max_atk is not None:
            add("c.atk <= $?", int(max_atk))
        if level is not None:
            add("c.level = $?", int(level))
        if rank is not None:
            add("c.rank = $?", int(rank))
        if linkval is not None:
            add("c.linkval = $?", int(linkval))

        safe_limit = max(1, min(int(limit), 25))
        values.append(safe_limit)
        where = " AND ".join(clauses) if clauses else "TRUE"
        rows = await self.pool.fetch(
            f"""
            SELECT c.*
            FROM cards c
            WHERE {where}
            ORDER BY COALESCE(c.name_fr, c.name_en)
            LIMIT ${len(values)}
            """,
            *values,
        )
        return [Card.from_record(dict(row)) for row in rows]

    async def diagnostic(self) -> DatabaseDiagnostic:
        async with self.pool.acquire() as connection:
            total_cards = int(await connection.fetchval("SELECT COUNT(*) FROM cards") or 0)
            missing_french_effect = int(
                await connection.fetchval(
                    "SELECT COUNT(*) FROM cards WHERE NULLIF(TRIM(COALESCE(description_fr, '')), '') IS NULL"
                ) or 0
            )
            missing_image = int(
                await connection.fetchval(
                    "SELECT COUNT(*) FROM cards WHERE NULLIF(TRIM(COALESCE(image_url, '')), '') IS NULL"
                ) or 0
            )
            missing_classification = int(
                await connection.fetchval(
                    "SELECT COUNT(*) FROM cards WHERE NULLIF(TRIM(COALESCE(classification, '')), '') IS NULL"
                ) or 0
            )
            missing_archetype = int(
                await connection.fetchval(
                    "SELECT COUNT(*) FROM cards WHERE NULLIF(TRIM(COALESCE(archetype, '')), '') IS NULL"
                ) or 0
            )
            roleless_cards = int(
                await connection.fetchval(
                    """
                    SELECT COUNT(*) FROM cards c
                    WHERE NOT EXISTS (
                        SELECT 1 FROM card_roles cr WHERE cr.card_id = c.ygoprodeck_id
                    )
                    """
                ) or 0
            )
            aliases = int(await connection.fetchval("SELECT COUNT(*) FROM card_aliases") or 0)
            strategic_roles = int(await connection.fetchval("SELECT COUNT(*) FROM card_roles") or 0)
            pending_submissions = int(
                await connection.fetchval(
                    "SELECT COUNT(*) FROM card_submissions WHERE status IN ('pending', 'processing')"
                ) or 0
            )
            exact_duplicate_names = int(
                await connection.fetchval(
                    """
                    WITH names AS (
                        SELECT ygoprodeck_id, LOWER(TRIM(name_en)) AS value FROM cards
                        UNION ALL
                        SELECT ygoprodeck_id, LOWER(TRIM(name_fr)) AS value
                        FROM cards WHERE NULLIF(TRIM(COALESCE(name_fr, '')), '') IS NOT NULL
                    ), duplicated AS (
                        SELECT value
                        FROM names
                        WHERE value <> ''
                        GROUP BY value
                        HAVING COUNT(DISTINCT ygoprodeck_id) > 1
                    )
                    SELECT COUNT(*) FROM duplicated
                    """
                ) or 0
            )
            empty_archetypes = int(
                await connection.fetchval(
                    """
                    SELECT COUNT(*)
                    FROM archetypes a
                    WHERE NOT EXISTS (
                        SELECT 1 FROM cards c
                        WHERE LOWER(COALESCE(c.archetype, '')) = LOWER(COALESCE(a.api_name, a.name))
                           OR LOWER(COALESCE(c.archetype, '')) = LOWER(a.name)
                    )
                    """
                ) or 0
            )
            combos_without_steps = int(
                await connection.fetchval(
                    """
                    SELECT COUNT(*) FROM combos co
                    WHERE NOT EXISTS (
                        SELECT 1 FROM combo_steps cs WHERE cs.combo_id = co.id
                    )
                    """
                ) or 0
            )
            last_discovery_at = await connection.fetchval(
                "SELECT MAX(discovered_at) FROM cards WHERE import_source = 'random_discovery'"
            )

        return DatabaseDiagnostic(
            total_cards=total_cards,
            missing_french_effect=missing_french_effect,
            missing_image=missing_image,
            missing_classification=missing_classification,
            missing_archetype=missing_archetype,
            roleless_cards=roleless_cards,
            aliases=aliases,
            strategic_roles=strategic_roles,
            pending_submissions=pending_submissions,
            exact_duplicate_names=exact_duplicate_names,
            empty_archetypes=empty_archetypes,
            combos_without_steps=combos_without_steps,
            last_discovery_at=last_discovery_at,
        )
