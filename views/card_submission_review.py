from __future__ import annotations

import contextlib
import logging
from typing import Any

import discord

from config import SETTINGS
from models.card_submission import CardSubmission, DuplicateMatch
from services.card_submission_service import (
    DuplicateDecisionError,
    SubmissionDecisionResult,
    SubmissionStateError,
)
from utils.embeds import card_embed, error_embed, success_embed
from utils.permissions import is_staff_member
from utils.text import truncate


LOGGER = logging.getLogger(__name__)


STATUS_LABELS = {
    "pending": "⏳ En attente",
    "processing": "🔄 Traitement en cours",
    "approved": "✅ Validée",
    "updated": "🔄 Fiche mise à jour",
    "needs_changes": "✏️ À corriger",
    "rejected": "❌ Refusée",
}

STATUS_COLOURS = {
    "pending": discord.Colour.orange(),
    "processing": discord.Colour.gold(),
    "approved": discord.Colour.green(),
    "updated": discord.Colour.blurple(),
    "needs_changes": discord.Colour.yellow(),
    "rejected": discord.Colour.red(),
}

DUPLICATE_LABELS = {
    "exact_id": "Même identifiant",
    "exact_name": "Même nom",
    "similar": "Nom ressemblant",
}


def duplicate_summary(duplicates: tuple[DuplicateMatch, ...]) -> str:
    if not duplicates:
        return "✅ Aucun doublon détecté dans PostgreSQL."

    lines: list[str] = []
    for duplicate in duplicates[:5]:
        label = DUPLICATE_LABELS.get(duplicate.match_type, "Ressemblance")
        score = f"{duplicate.score * 100:.0f} %"
        lines.append(
            f"• **{label}** — {duplicate.display_name} "
            f"(`{duplicate.card_id}` · {score})"
        )
    return "\n".join(lines)


def submission_embed(
    submission: CardSubmission,
    *,
    existing_image_url: str | None = None,
) -> discord.Embed:
    embed = card_embed(submission.candidate)
    embed.description = truncate(submission.candidate.display_description, 2400)
    embed.title = f"Proposition #{submission.id} — {submission.candidate.display_name}"
    embed.colour = STATUS_COLOURS.get(submission.status, discord.Colour.greyple())
    embed.add_field(
        name="État de la demande",
        value=STATUS_LABELS.get(submission.status, submission.status),
        inline=True,
    )
    embed.add_field(
        name="Proposée par",
        value=f"<@{submission.submitted_by}> (`{submission.submitted_by}`)",
        inline=True,
    )
    embed.add_field(
        name="Source",
        value=(
            f"**{submission.source_type.upper()}**\n"
            f"{truncate(submission.source_reference or 'Aucune référence', 900)}"
        ),
        inline=False,
    )
    embed.add_field(
        name="Détection des doublons",
        value=duplicate_summary(submission.duplicates),
        inline=False,
    )
    if submission.review_reason:
        embed.add_field(
            name="Décision du staff",
            value=truncate(submission.review_reason, 1000),
            inline=False,
        )
    if submission.reviewed_by:
        embed.add_field(
            name="Examinée par",
            value=f"<@{submission.reviewed_by}> (`{submission.reviewed_by}`)",
            inline=True,
        )
    if existing_image_url:
        embed.set_image(url=existing_image_url)
    elif submission.candidate.image_url:
        embed.set_image(url=submission.candidate.image_url)
    embed.set_footer(
        text=(
            f"Demande #{submission.id} • Carte {submission.candidate.ygoprodeck_id} • "
            "Aucune insertion avant validation"
        )
    )
    return embed


async def _staff_allowed(interaction: discord.Interaction) -> bool:
    if is_staff_member(
        interaction.user,
        configured_role_ids=SETTINGS.staff_role_ids,
    ):
        return True
    await interaction.response.send_message(
        embed=error_embed(
            "Permission refusée",
            "Seul le staff peut examiner cette proposition.",
        ),
        ephemeral=True,
    )
    return False


class ReviewReasonModal(discord.ui.Modal):
    def __init__(
        self,
        *,
        view: "CardSubmissionReviewView",
        action: str,
    ) -> None:
        title = "Demander une correction" if action == "needs_changes" else "Refuser la carte"
        super().__init__(
            title=title,
            custom_id=f"rilliona:submission:{view.submission_id}:{action}:modal",
            timeout=300,
        )
        self.review_view = view
        self.action = action
        self.reason = discord.ui.TextInput(
            label="Raison",
            placeholder=(
                "Explique précisément ce que la personne doit corriger."
                if action == "needs_changes"
                else "Explique pourquoi la proposition est refusée."
            ),
            style=discord.TextStyle.paragraph,
            min_length=3,
            max_length=1000,
            required=True,
        )
        self.add_item(self.reason)

    async def on_submit(self, interaction: discord.Interaction) -> None:
        if not await _staff_allowed(interaction):
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        service = self.review_view.bot.card_submission_service
        try:
            if self.action == "needs_changes":
                result = await service.request_changes(
                    self.review_view.submission_id,
                    reviewed_by=interaction.user.id,
                    reason=str(self.reason),
                )
                title = "Corrections demandées"
                description = "La proposition est fermée. Le membre devra en envoyer une nouvelle version corrigée."
            else:
                result = await service.reject(
                    self.review_view.submission_id,
                    reviewed_by=interaction.user.id,
                    reason=str(self.reason),
                )
                title = "Proposition refusée"
                description = "La carte n'a pas été ajoutée à la base."
        except (ValueError, SubmissionStateError) as error:
            await interaction.followup.send(
                embed=error_embed("Action impossible", str(error)),
                ephemeral=True,
            )
            return
        except Exception:
            LOGGER.exception("Échec de la décision sur la demande %s", self.review_view.submission_id)
            await interaction.followup.send(
                embed=error_embed(
                    "Action temporairement indisponible",
                    "La décision n'a pas pu être enregistrée.",
                ),
                ephemeral=True,
            )
            return

        await self.review_view.refresh_messages(interaction, result.submission)
        await self.review_view.notify_submitter(result.submission)
        await interaction.followup.send(
            embed=success_embed(title, description),
            ephemeral=True,
        )


class CardSubmissionReviewView(discord.ui.View):
    def __init__(
        self,
        bot: Any,
        submission_id: int,
        *,
        disabled: bool = False,
    ) -> None:
        super().__init__(timeout=None)
        self.bot = bot
        self.submission_id = submission_id

        approve = discord.ui.Button(
            label="Valider",
            emoji="✅",
            style=discord.ButtonStyle.success,
            custom_id=f"rilliona:submission:{submission_id}:approve",
            disabled=disabled,
        )
        update = discord.ui.Button(
            label="Mettre à jour",
            emoji="🔄",
            style=discord.ButtonStyle.primary,
            custom_id=f"rilliona:submission:{submission_id}:update",
            disabled=disabled,
        )
        changes = discord.ui.Button(
            label="À corriger",
            emoji="✏️",
            style=discord.ButtonStyle.secondary,
            custom_id=f"rilliona:submission:{submission_id}:changes",
            disabled=disabled,
        )
        reject = discord.ui.Button(
            label="Refuser",
            emoji="❌",
            style=discord.ButtonStyle.danger,
            custom_id=f"rilliona:submission:{submission_id}:reject",
            disabled=disabled,
        )

        approve.callback = self._approve_callback
        update.callback = self._update_callback
        changes.callback = self._changes_callback
        reject.callback = self._reject_callback

        self.add_item(approve)
        self.add_item(update)
        self.add_item(changes)
        self.add_item(reject)

    async def _approve_callback(self, interaction: discord.Interaction) -> None:
        await self._approve_or_update(interaction, update_existing=False)

    async def _update_callback(self, interaction: discord.Interaction) -> None:
        await self._approve_or_update(interaction, update_existing=True)

    async def _changes_callback(self, interaction: discord.Interaction) -> None:
        if not await _staff_allowed(interaction):
            return
        await interaction.response.send_modal(
            ReviewReasonModal(view=self, action="needs_changes")
        )

    async def _reject_callback(self, interaction: discord.Interaction) -> None:
        if not await _staff_allowed(interaction):
            return
        await interaction.response.send_modal(
            ReviewReasonModal(view=self, action="rejected")
        )

    async def _approve_or_update(
        self,
        interaction: discord.Interaction,
        *,
        update_existing: bool,
    ) -> None:
        if not await _staff_allowed(interaction):
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            result: SubmissionDecisionResult = await self.bot.card_submission_service.approve(
                self.submission_id,
                reviewed_by=interaction.user.id,
                update_existing=update_existing,
            )
        except (DuplicateDecisionError, SubmissionStateError, ValueError) as error:
            await interaction.followup.send(
                embed=error_embed("Action impossible", str(error)),
                ephemeral=True,
            )
            return
        except Exception:
            LOGGER.exception("Échec de la validation de la demande %s", self.submission_id)
            await interaction.followup.send(
                embed=error_embed(
                    "Validation temporairement indisponible",
                    "Le traitement n'a pas pu être confirmé complètement. Consulte de nouveau la demande avec `/base examiner_demande`.",
                ),
                ephemeral=True,
            )
            return

        await self.refresh_messages(interaction, result.submission)
        await self.notify_submitter(result.submission)

        verification = result.verification
        verification_text = verification.summary if verification else "Vérification non disponible."
        action = "mise à jour" if update_existing else "ajoutée"
        journal_text = (
            f"Journal d'import : **#{result.import_log_id}**"
            if result.import_log_id is not None
            else "Journal d'import secondaire indisponible"
        )
        await interaction.followup.send(
            embed=success_embed(
                f"Carte {action}",
                f"**{result.submission.candidate.display_name}** est maintenant enregistrée.\n\n"
                f"{verification_text}\n\n{journal_text}",
            ),
            ephemeral=True,
        )

    @staticmethod
    def _image_from_message(message: discord.Message | None) -> str | None:
        if message is None or not message.embeds:
            return None
        image = message.embeds[0].image
        return image.url if image and image.url else None

    async def refresh_messages(
        self,
        interaction: discord.Interaction,
        submission: CardSubmission,
    ) -> None:
        disabled_view = CardSubmissionReviewView(
            self.bot,
            submission.id,
            disabled=True,
        )
        current_message = interaction.message
        current_image = self._image_from_message(current_message)
        if current_message is not None:
            with contextlib.suppress(discord.HTTPException):
                await current_message.edit(
                    embed=submission_embed(
                        submission,
                        existing_image_url=current_image,
                    ),
                    view=disabled_view,
                )

        if (
            submission.review_channel_id is None
            or submission.review_message_id is None
            or (
                current_message is not None
                and current_message.id == submission.review_message_id
            )
        ):
            return

        try:
            channel = self.bot.get_channel(submission.review_channel_id)
            if channel is None:
                channel = await self.bot.fetch_channel(submission.review_channel_id)
            if not hasattr(channel, "fetch_message"):
                return
            review_message = await channel.fetch_message(submission.review_message_id)
            review_image = self._image_from_message(review_message)
            await review_message.edit(
                embed=submission_embed(
                    submission,
                    existing_image_url=review_image,
                ),
                view=disabled_view,
            )
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            LOGGER.warning(
                "Impossible de mettre à jour le message de revue de la demande %s",
                submission.id,
            )

    async def notify_submitter(self, submission: CardSubmission) -> None:
        status = STATUS_LABELS.get(submission.status, submission.status)
        reason = f"\nRaison : {submission.review_reason}" if submission.review_reason else ""
        try:
            user = self.bot.get_user(submission.submitted_by)
            if user is None:
                user = await self.bot.fetch_user(submission.submitted_by)
            await user.send(
                f"Ta proposition **#{submission.id} — {submission.candidate.display_name}** "
                f"a été examinée : **{status}**.{reason}"
            )
        except (discord.Forbidden, discord.NotFound, discord.HTTPException):
            pass
