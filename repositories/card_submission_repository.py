from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable

import asyncpg

from models.card import Card
from models.card_submission import CardSubmission, DuplicateMatch, card_to_payload


class CardSubmissionRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self.pool = pool

    async def create(
        self,
        *,
        candidate: Card,
        submitted_by: int,
        guild_id: int | None,
        source_type: str,
        source_reference: str | None,
        original_filename: str | None,
        pending_image_path: Path | None,
        duplicates: Iterable[DuplicateMatch],
        duplicate_status: str,
    ) -> CardSubmission:
        duplicate_payload = [item.to_payload() for item in duplicates]
        row = await self.pool.fetchrow(
            """
            INSERT INTO card_submissions (
                candidate_card_id,
                submitted_by,
                guild_id,
                source_type,
                source_reference,
                original_filename,
                pending_image_path,
                candidate_data,
                duplicate_data,
                duplicate_status,
                status
            )
            VALUES (
                $1, $2, $3, $4, $5, $6, $7,
                $8::jsonb, $9::jsonb, $10, 'pending'
            )
            RETURNING *
            """,
            candidate.ygoprodeck_id,
            submitted_by,
            guild_id,
            source_type,
            source_reference,
            original_filename,
            str(pending_image_path) if pending_image_path else None,
            json.dumps(card_to_payload(candidate), ensure_ascii=False),
            json.dumps(duplicate_payload, ensure_ascii=False),
            duplicate_status,
        )
        if row is None:
            raise RuntimeError("La demande de carte n'a pas pu être enregistrée.")
        return CardSubmission.from_record(dict(row))

    async def find_active_by_candidate(
        self,
        candidate_card_id: int,
    ) -> CardSubmission | None:
        row = await self.pool.fetchrow(
            """
            SELECT *
            FROM card_submissions
            WHERE candidate_card_id = $1
              AND status IN ('pending', 'processing')
            ORDER BY created_at ASC
            LIMIT 1
            """,
            candidate_card_id,
        )
        return CardSubmission.from_record(dict(row)) if row else None

    async def get(self, submission_id: int) -> CardSubmission | None:
        row = await self.pool.fetchrow(
            "SELECT * FROM card_submissions WHERE id = $1",
            submission_id,
        )
        return CardSubmission.from_record(dict(row)) if row else None

    async def list_actionable(self, limit: int = 100) -> list[CardSubmission]:
        rows = await self.pool.fetch(
            """
            SELECT *
            FROM card_submissions
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT $1
            """,
            limit,
        )
        return [CardSubmission.from_record(dict(row)) for row in rows]

    async def list_pending(self, limit: int = 25) -> list[CardSubmission]:
        rows = await self.pool.fetch(
            """
            SELECT *
            FROM card_submissions
            WHERE status = 'pending'
            ORDER BY created_at ASC
            LIMIT $1
            """,
            limit,
        )
        return [CardSubmission.from_record(dict(row)) for row in rows]

    async def count_pending(self) -> int:
        return int(
            await self.pool.fetchval(
                "SELECT COUNT(*) FROM card_submissions WHERE status = 'pending'"
            )
            or 0
        )

    async def set_review_message(
        self,
        submission_id: int,
        *,
        channel_id: int,
        message_id: int,
    ) -> CardSubmission:
        row = await self.pool.fetchrow(
            """
            UPDATE card_submissions
            SET review_channel_id = $2,
                review_message_id = $3,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $1
            RETURNING *
            """,
            submission_id,
            channel_id,
            message_id,
        )
        if row is None:
            raise LookupError("Demande de carte introuvable.")
        return CardSubmission.from_record(dict(row))

    async def claim(
        self,
        submission_id: int,
        *,
        reviewed_by: int,
    ) -> CardSubmission | None:
        row = await self.pool.fetchrow(
            """
            UPDATE card_submissions
            SET status = 'processing',
                reviewed_by = $2,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $1
              AND status = 'pending'
            RETURNING *
            """,
            submission_id,
            reviewed_by,
        )
        return CardSubmission.from_record(dict(row)) if row else None

    async def finalize_claim(
        self,
        submission_id: int,
        *,
        new_status: str,
        reviewed_by: int,
        reason: str | None,
    ) -> CardSubmission | None:
        row = await self.pool.fetchrow(
            """
            UPDATE card_submissions
            SET status = $2,
                reviewed_by = $3,
                review_reason = $4,
                reviewed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $1
              AND status = 'processing'
            RETURNING *
            """,
            submission_id,
            new_status,
            reviewed_by,
            reason,
        )
        return CardSubmission.from_record(dict(row)) if row else None

    async def release_claim(self, submission_id: int) -> None:
        await self.pool.execute(
            """
            UPDATE card_submissions
            SET status = 'pending',
                reviewed_by = NULL,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $1
              AND status = 'processing'
            """,
            submission_id,
        )

    async def resolve(
        self,
        submission_id: int,
        *,
        expected_statuses: tuple[str, ...],
        new_status: str,
        reviewed_by: int,
        reason: str | None,
    ) -> CardSubmission | None:
        row = await self.pool.fetchrow(
            """
            UPDATE card_submissions
            SET status = $2,
                reviewed_by = $3,
                review_reason = $4,
                reviewed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $1
              AND status = ANY($5::TEXT[])
            RETURNING *
            """,
            submission_id,
            new_status,
            reviewed_by,
            reason,
            list(expected_statuses),
        )
        return CardSubmission.from_record(dict(row)) if row else None

    async def update_pending_image_path(
        self,
        submission_id: int,
        path: Path | None,
    ) -> None:
        await self.pool.execute(
            """
            UPDATE card_submissions
            SET pending_image_path = $2,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = $1
            """,
            submission_id,
            str(path) if path else None,
        )
