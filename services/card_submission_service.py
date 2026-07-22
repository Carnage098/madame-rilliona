from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass, replace
from pathlib import Path
from uuid import uuid4

from models.card import Card
from models.card_submission import CardSubmission, DuplicateMatch
from repositories.card_repository import CardRepository
from repositories.card_submission_repository import CardSubmissionRepository
from services.card_catalog_service import CardCatalogService
from services.card_image_service import CardImageService, PNG_SIGNATURE
from services.card_import_service import (
    CardImportService,
    CardVerificationResult,
)


class SubmissionStateError(RuntimeError):
    """La demande a déjà été traitée ou ne peut pas recevoir cette action."""


class DuplicateDecisionError(ValueError):
    """Le choix du staff n'est pas compatible avec les doublons détectés."""


@dataclass(frozen=True, slots=True)
class SubmissionDecisionResult:
    submission: CardSubmission
    card: Card | None = None
    verification: CardVerificationResult | None = None
    import_log_id: int | None = None


class CardSubmissionService:
    """Prépare les propositions publiques et applique les décisions du staff."""

    def __init__(
        self,
        *,
        catalog: CardCatalogService,
        cards: CardRepository,
        submissions: CardSubmissionRepository,
        images: CardImageService,
        imports: CardImportService,
        max_image_bytes: int,
    ) -> None:
        self.catalog = catalog
        self.cards = cards
        self.submissions = submissions
        self.images = images
        self.imports = imports
        self.max_image_bytes = max_image_bytes

    @staticmethod
    def _clean_reference(value: str | None, *, limit: int = 2048) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned[:limit] or None

    @staticmethod
    def _duplicate_status(duplicates: tuple[DuplicateMatch, ...]) -> str:
        kinds = {item.match_type for item in duplicates}
        if "exact_id" in kinds:
            return "exact_id"
        if "exact_name" in kinds:
            return "exact_name"
        if "similar" in kinds:
            return "similar"
        return "none"

    async def _prepare_candidate(
        self,
        identifier: str,
        *,
        submitted_by: int,
        source_type: str,
    ) -> tuple[Card, tuple[DuplicateMatch, ...]]:
        candidate = await self.catalog.resolve_candidate(
            identifier,
            import_source=f"pending_{source_type}:{submitted_by}",
        )
        if candidate is None:
            raise ValueError(
                "La carte n'a pas été reconnue dans YGOPRODeck. "
                "Vérifie son nom officiel ou son identifiant."
            )
        duplicates = tuple(await self.cards.duplicate_candidates(candidate, limit=5))
        return candidate, duplicates

    async def _ensure_no_active_submission(self, candidate: Card) -> None:
        existing = await self.submissions.find_active_by_candidate(
            candidate.ygoprodeck_id
        )
        if existing is not None:
            raise ValueError(
                f"Une proposition pour cette carte est déjà en attente : demande #{existing.id}."
            )

    async def submit_from_url(
        self,
        *,
        url: str,
        name_hint: str | None,
        submitted_by: int,
        guild_id: int | None,
    ) -> CardSubmission:
        identifier = CardImportService.identifier_from_url(url, name_hint=name_hint)
        candidate, duplicates = await self._prepare_candidate(
            identifier,
            submitted_by=submitted_by,
            source_type="url",
        )
        await self._ensure_no_active_submission(candidate)
        return await self.submissions.create(
            candidate=candidate,
            submitted_by=submitted_by,
            guild_id=guild_id,
            source_type="url",
            source_reference=self._clean_reference(url),
            original_filename=None,
            pending_image_path=None,
            duplicates=duplicates,
            duplicate_status=self._duplicate_status(duplicates),
        )

    async def submit_from_png(
        self,
        *,
        content: bytes,
        filename: str,
        content_type: str | None,
        declared_size: int,
        name_hint: str | None,
        submitted_by: int,
        guild_id: int | None,
    ) -> CardSubmission:
        if declared_size > self.max_image_bytes or len(content) > self.max_image_bytes:
            max_mb = self.max_image_bytes / (1024 * 1024)
            raise ValueError(f"L'image dépasse la limite de {max_mb:.1f} Mo.")
        if not filename.casefold().endswith(".png"):
            raise ValueError("Le fichier doit avoir l'extension .png.")
        if content_type and content_type.casefold() not in {
            "image/png",
            "image/x-png",
            "application/octet-stream",
        }:
            raise ValueError("Le fichier transmis n'est pas déclaré comme une image PNG.")
        if not content.startswith(PNG_SIGNATURE):
            raise ValueError("Le contenu du fichier n'est pas un véritable PNG.")

        identifier = CardImportService.identifier_from_filename(
            filename,
            name_hint=name_hint,
        )
        candidate, duplicates = await self._prepare_candidate(
            identifier,
            submitted_by=submitted_by,
            source_type="png",
        )
        await self._ensure_no_active_submission(candidate)

        pending_path: Path | None = None
        try:
            pending_path = await self.images.save_pending_png(uuid4().hex, content)
            return await self.submissions.create(
                candidate=candidate,
                submitted_by=submitted_by,
                guild_id=guild_id,
                source_type="png",
                source_reference=f"discord-attachment:{filename}"[:2048],
                original_filename=filename[:255],
                pending_image_path=pending_path,
                duplicates=duplicates,
                duplicate_status=self._duplicate_status(duplicates),
            )
        except Exception:
            if pending_path is not None:
                await self.images.delete_pending_png(pending_path)
            raise

    async def _write_import_log(
        self,
        *,
        submission: CardSubmission,
        status: str,
        verification: CardVerificationResult,
        reviewed_by: int,
    ) -> int:
        details = {
            **verification.checks,
            "submission_id": submission.id,
            "reviewed_by": reviewed_by,
            "duplicate_status": submission.duplicate_status,
        }
        return await self.cards.record_import(
            card_id=submission.candidate.ygoprodeck_id,
            submitted_by=submission.submitted_by,
            source_type=f"validated_{submission.source_type}",
            source_reference=submission.source_reference,
            original_filename=submission.original_filename,
            status=status,
            verification_status=(
                "verified" if verification.verified else "incomplete"
            ),
            details=json.dumps(details, ensure_ascii=False),
        )

    async def approve(
        self,
        submission_id: int,
        *,
        reviewed_by: int,
        update_existing: bool,
    ) -> SubmissionDecisionResult:
        claimed = await self.submissions.claim(
            submission_id,
            reviewed_by=reviewed_by,
        )
        if claimed is None:
            raise SubmissionStateError(
                "Cette demande a déjà été traitée ou est actuellement examinée."
            )

        card_written = False
        final_status = "updated" if update_existing else "approved"
        try:
            exact_id = claimed.exact_id_duplicate
            exact_names = claimed.exact_name_duplicates
            if update_existing and exact_id is None:
                raise DuplicateDecisionError(
                    "Aucune fiche portant le même identifiant n'existe. "
                    "Utilise **Valider** pour créer cette carte."
                )
            if not update_existing and exact_id is not None:
                raise DuplicateDecisionError(
                    "Cette carte existe déjà avec le même identifiant. "
                    "Utilise **Mettre à jour**."
                )
            if not update_existing and exact_names:
                names = ", ".join(item.display_name for item in exact_names[:3])
                raise DuplicateDecisionError(
                    "Un nom identique appartient déjà à une autre fiche : "
                    f"{names}. Vérifie la demande avant de la valider."
                )

            pending_png: bytes | None = None
            if claimed.pending_image_path is not None:
                pending_png = await self.images.read_pending_png(
                    claimed.pending_image_path
                )

            action = "update" if update_existing else "approved"
            card = replace(
                claimed.candidate,
                import_source=f"staff_{action}_submission:{claimed.id}",
            )
            await self.cards.upsert(card)
            card_written = True

            require_local_png = pending_png is not None
            if pending_png is not None:
                await self.images.save_staff_png(card.ygoprodeck_id, pending_png)
                await self.images.delete_pending_png(claimed.pending_image_path)
                await self.submissions.update_pending_image_path(claimed.id, None)

            verification = await self.imports.verify_card(
                card.ygoprodeck_id,
                require_local_png=require_local_png,
            )
            log_id: int | None = None
            with contextlib.suppress(Exception):
                log_id = await self._write_import_log(
                    submission=claimed,
                    status=final_status,
                    verification=verification,
                    reviewed_by=reviewed_by,
                )

            finalized = await self.submissions.finalize_claim(
                claimed.id,
                new_status=final_status,
                reviewed_by=reviewed_by,
                reason=(
                    "Fiche existante mise à jour après validation du staff."
                    if update_existing
                    else "Carte validée par le staff."
                ),
            )
            if finalized is None:
                raise SubmissionStateError(
                    "La carte est enregistrée, mais le statut de la demande n'a pas pu être finalisé."
                )
            return SubmissionDecisionResult(
                submission=finalized,
                card=verification.card or card,
                verification=verification,
                import_log_id=log_id,
            )
        except Exception:
            if not card_written:
                await self.submissions.release_claim(submission_id)
            else:
                # Ne jamais remettre en attente une demande dont la carte a déjà été écrite.
                with contextlib.suppress(Exception):
                    await self.submissions.finalize_claim(
                        submission_id,
                        new_status=final_status,
                        reviewed_by=reviewed_by,
                        reason=(
                            "Carte enregistrée, mais le contrôle technique final est incomplet."
                        ),
                    )
            raise

    async def reject(
        self,
        submission_id: int,
        *,
        reviewed_by: int,
        reason: str,
    ) -> SubmissionDecisionResult:
        cleaned_reason = reason.strip()[:1000]
        if not cleaned_reason:
            raise ValueError("Indique la raison du refus.")
        resolved = await self.submissions.resolve(
            submission_id,
            expected_statuses=("pending",),
            new_status="rejected",
            reviewed_by=reviewed_by,
            reason=cleaned_reason,
        )
        if resolved is None:
            raise SubmissionStateError("Cette demande a déjà été traitée.")
        await self.images.delete_pending_png(resolved.pending_image_path)
        await self.submissions.update_pending_image_path(resolved.id, None)
        refreshed = await self.submissions.get(resolved.id)
        return SubmissionDecisionResult(submission=refreshed or resolved)

    async def request_changes(
        self,
        submission_id: int,
        *,
        reviewed_by: int,
        reason: str,
    ) -> SubmissionDecisionResult:
        cleaned_reason = reason.strip()[:1000]
        if not cleaned_reason:
            raise ValueError("Indique ce que le membre doit corriger.")
        resolved = await self.submissions.resolve(
            submission_id,
            expected_statuses=("pending",),
            new_status="needs_changes",
            reviewed_by=reviewed_by,
            reason=cleaned_reason,
        )
        if resolved is None:
            raise SubmissionStateError("Cette demande a déjà été traitée.")
        # La personne devra créer une nouvelle proposition corrigée.
        await self.images.delete_pending_png(resolved.pending_image_path)
        await self.submissions.update_pending_image_path(resolved.id, None)
        refreshed = await self.submissions.get(resolved.id)
        return SubmissionDecisionResult(submission=refreshed or resolved)

    async def cleanup_orphan_pending_image(self, path: Path | None) -> None:
        with contextlib.suppress(Exception):
            await self.images.delete_pending_png(path)
