from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from config import SETTINGS
from models.card_submission import CardSubmission
from utils.embeds import card_embed, error_embed, success_embed
from views.card_submission_review import (
    CardSubmissionReviewView,
    duplicate_summary,
    submission_embed,
)


LOGGER = logging.getLogger(__name__)


class CardCog(
    commands.GroupCog,
    group_name="carte",
    group_description="Consulter le catalogue de cartes",
):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def card_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ):
        del interaction
        try:
            suggestions = await self.bot.card_catalog_service.autocomplete(current)
        except Exception:
            LOGGER.exception("Échec de l'autocomplétion pour %r", current)
            suggestions = []

        return [
            app_commands.Choice(
                name=suggestion.display_name[:100],
                value=str(suggestion.card_id),
            )
            for suggestion in suggestions[:25]
        ]

    async def _post_review_message(self, submission: CardSubmission) -> bool:
        channel_id = SETTINGS.card_review_channel_id
        if channel_id is None:
            return False

        try:
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                channel = await self.bot.fetch_channel(channel_id)
            if not hasattr(channel, "send"):
                raise TypeError("Le salon configuré ne permet pas l'envoi de messages.")

            embed = submission_embed(submission)
            view = CardSubmissionReviewView(self.bot, submission.id)
            file: discord.File | None = None
            if (
                submission.pending_image_path is not None
                and submission.pending_image_path.is_file()
            ):
                filename = f"proposition_{submission.id}.png"
                file = discord.File(submission.pending_image_path, filename=filename)
                embed.set_image(url=f"attachment://{filename}")

            if file is None:
                message = await channel.send(embed=embed, view=view)
            else:
                message = await channel.send(embed=embed, view=view, file=file)

            await self.bot.card_submission_repository.set_review_message(
                submission.id,
                channel_id=message.channel.id,
                message_id=message.id,
            )
            return True
        except (discord.Forbidden, discord.NotFound, discord.HTTPException, TypeError):
            LOGGER.exception(
                "Impossible d'envoyer la proposition %s dans le salon de validation",
                submission.id,
            )
            return False

    @app_commands.command(name="rechercher", description="Rechercher une carte Yu-Gi-Oh!")
    @app_commands.describe(carte="Nom français, nom anglais ou identifiant de la carte")
    @app_commands.autocomplete(carte=card_autocomplete)
    async def search_card(
        self,
        interaction: discord.Interaction,
        carte: str,
    ) -> None:
        await interaction.response.defer(thinking=True)

        try:
            card = await self.bot.card_catalog_service.find_or_fetch(carte)
        except Exception:
            LOGGER.exception("Échec de la recherche de carte pour %r", carte)
            await interaction.followup.send(
                embed=error_embed(
                    "Recherche temporairement indisponible",
                    "La base externe n'a pas répondu correctement. Réessaie dans quelques instants.",
                ),
                ephemeral=True,
            )
            return

        if card is None:
            await interaction.followup.send(
                embed=error_embed(
                    "Carte introuvable",
                    "Vérifie l'orthographe du nom français ou anglais.",
                ),
                ephemeral=True,
            )
            return

        embed = card_embed(card)
        try:
            image_path = await self.bot.card_image_service.get(card)
        except Exception:
            LOGGER.exception(
                "Impossible de récupérer l'image de la carte %s",
                card.ygoprodeck_id,
            )
            image_path = None

        if image_path:
            file = discord.File(image_path, filename=image_path.name)
            embed.set_image(url=f"attachment://{image_path.name}")
            await interaction.followup.send(embed=embed, file=file)
        else:
            if card.image_url:
                embed.set_image(url=card.image_url)
            await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="proposer",
        description="Proposer une carte au staff depuis un site ou une image PNG",
    )
    @app_commands.guild_only()
    @app_commands.describe(
        source="Choisir entre une URL et une image PNG",
        nom="Nom français/anglais ou ID, conseillé pour un PNG",
        url="Page de la carte ou URL de référence",
        image="Image PNG de la carte",
    )
    @app_commands.choices(
        source=[
            app_commands.Choice(name="Site internet", value="url"),
            app_commands.Choice(name="Image PNG", value="png"),
        ]
    )
    async def propose_card(
        self,
        interaction: discord.Interaction,
        source: app_commands.Choice[str],
        nom: str | None = None,
        url: str | None = None,
        image: discord.Attachment | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            if source.value == "url":
                if not url:
                    raise ValueError("Renseigne l'option `url`.")
                if image is not None:
                    raise ValueError("N'envoie pas d'image avec la source Site internet.")
                submission = await self.bot.card_submission_service.submit_from_url(
                    url=url,
                    name_hint=nom,
                    submitted_by=interaction.user.id,
                    guild_id=interaction.guild_id,
                )
            elif source.value == "png":
                if image is None:
                    raise ValueError("Ajoute un fichier dans l'option `image`.")
                if url:
                    raise ValueError("Ne renseigne pas d'URL avec la source Image PNG.")
                if image.size > SETTINGS.max_staff_image_bytes:
                    maximum = SETTINGS.max_staff_image_bytes / (1024 * 1024)
                    raise ValueError(f"L'image dépasse la limite de {maximum:.1f} Mo.")
                content = await image.read(use_cached=True)
                submission = await self.bot.card_submission_service.submit_from_png(
                    content=content,
                    filename=image.filename,
                    content_type=image.content_type,
                    declared_size=image.size,
                    name_hint=nom,
                    submitted_by=interaction.user.id,
                    guild_id=interaction.guild_id,
                )
            else:
                raise ValueError("La source sélectionnée n'est pas reconnue.")
        except ValueError as error:
            await interaction.followup.send(
                embed=error_embed("Proposition impossible", str(error)),
                ephemeral=True,
            )
            return
        except discord.HTTPException as error:
            await interaction.followup.send(
                embed=error_embed(
                    "Image inaccessible",
                    f"Discord n'a pas permis de lire le fichier : {error}",
                ),
                ephemeral=True,
            )
            return
        except Exception:
            LOGGER.exception("Échec de la proposition d'une carte")
            await interaction.followup.send(
                embed=error_embed(
                    "Proposition temporairement indisponible",
                    "La carte n'a pas pu être préparée. Réessaie dans quelques instants.",
                ),
                ephemeral=True,
            )
            return

        posted = await self._post_review_message(submission)
        review_location = (
            f"Elle a été transmise dans <#{SETTINGS.card_review_channel_id}>."
            if posted and SETTINGS.card_review_channel_id is not None
            else (
                "Elle est enregistrée dans la file d'attente. Le staff peut l'ouvrir "
                "avec `/base examiner_demande`."
            )
        )
        await interaction.followup.send(
            embed=success_embed(
                "Proposition enregistrée",
                f"**Demande #{submission.id} — {submission.candidate.display_name}**\n\n"
                "La carte n'a pas encore été ajoutée au catalogue. "
                f"{review_location}\n\n"
                f"**Contrôle des doublons**\n{duplicate_summary(submission.duplicates)}",
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="archetype",
        description="Lister les cartes d'un archétype et les importer si nécessaire",
    )
    async def cards_by_archetype(
        self,
        interaction: discord.Interaction,
        nom: str,
    ) -> None:
        await interaction.response.defer(thinking=True)

        entry = await self.bot.archetype_repository.get_by_name(nom)
        catalogue_name = entry.catalogue_name if entry else nom
        cards = await self.bot.card_repository.list_by_archetype(catalogue_name)

        if not cards:
            try:
                sync = await self.bot.card_catalog_service.synchronize_archetype(
                    catalogue_name
                )
                catalogue_name = sync.canonical_name
                cards = await self.bot.card_repository.list_by_archetype(
                    catalogue_name
                )
                if entry is not None:
                    await self.bot.archetype_repository.mark_cards_synced(
                        entry.id,
                        api_name=sync.canonical_name,
                    )
            except ValueError as error:
                await interaction.followup.send(
                    embed=error_embed("Archétype introuvable", str(error)),
                    ephemeral=True,
                )
                return
            except Exception:
                LOGGER.exception(
                    "Échec de l'import automatique de l'archétype %r",
                    catalogue_name,
                )
                await interaction.followup.send(
                    embed=error_embed(
                        "Import impossible",
                        "La base externe n'a pas répondu correctement.",
                    ),
                    ephemeral=True,
                )
                return

        if not cards:
            await interaction.followup.send(
                embed=error_embed(
                    "Aucune carte",
                    "Aucune carte n'a été trouvée pour cet archétype.",
                ),
                ephemeral=True,
            )
            return

        lines: list[str] = []
        for card in cards:
            category = card.card_category or "Non classée"
            section = card.deck_section or "Section inconnue"
            lines.append(
                f"• **{card.display_name}** — {category} / {section} (`{card.ygoprodeck_id}`)"
            )

        description = ""
        displayed = 0
        for line in lines:
            candidate = f"{description}\n{line}" if description else line
            if len(candidate) > 3900:
                break
            description = candidate
            displayed += 1

        total = await self.bot.card_repository.count_by_archetype(catalogue_name)
        if displayed < total:
            description += f"\n\n… et **{total - displayed}** autre(s) carte(s) enregistrée(s)."

        embed = discord.Embed(
            title=f"🎴 Cartes — {catalogue_name}",
            description=description,
            colour=discord.Colour.purple(),
        )
        embed.set_footer(
            text=f"{total} carte(s) enregistrée(s) • {displayed} affichée(s)"
        )
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CardCog(bot))
