from __future__ import annotations

from typing import TYPE_CHECKING

import time

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from bot import MadameRillionaBot
from services.card_api_service import CardApiError


class CardAdminCog(
    commands.GroupCog,
    group_name="base",
    group_description="Administration de la base de données de Madame Rilliona.",
):
    def __init__(self, bot: MadameRillionaBot) -> None:
        self.bot = bot

    @app_commands.command(
        name="synchroniser_cartes",
        description="Télécharge et met à jour le catalogue Yu-Gi-Oh! complet.",
    )
    @app_commands.checks.has_permissions(manage_guild=True)
    async def synchroniser_cartes(
        self,
        interaction: discord.Interaction,
    ) -> None:
        if self.bot.card_catalog.sync_in_progress:
            await interaction.response.send_message(
                "⏳ Une synchronisation est déjà en cours.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            thinking=True,
            ephemeral=True,
        )

        started_at = time.monotonic()

        try:
            report = await self.bot.card_catalog.sync_all()
        except CardApiError as exc:
            await interaction.edit_original_response(
                content=(
                    "❌ La synchronisation avec YGOPRODeck a échoué.\n"
                    f"`{exc}`"
                )
            )
            return
        except RuntimeError as exc:
            await interaction.edit_original_response(
                content=f"⚠️ {exc}"
            )
            return

        elapsed = time.monotonic() - started_at

        embed = discord.Embed(
            title="📚 Synchronisation terminée",
            colour=discord.Colour.green(),
        )
        embed.add_field(
            name="Catalogue anglais reçu",
            value=f"{report.english_received:,}".replace(",", " "),
        )
        embed.add_field(
            name="Traductions françaises reçues",
            value=f"{report.french_received:,}".replace(",", " "),
        )
        embed.add_field(
            name="Fiches traitées",
            value=f"{report.processed:,}".replace(",", " "),
        )
        embed.add_field(
            name="Nouvelles cartes",
            value=f"{report.new_cards:,}".replace(",", " "),
        )
        embed.add_field(
            name="Total local",
            value=f"{report.after_count:,}".replace(",", " "),
        )
        embed.add_field(
            name="Durée",
            value=f"{elapsed:.1f} secondes",
        )

        await interaction.edit_original_response(embed=embed)

    @synchroniser_cartes.error
    async def synchroniser_cartes_error(
        self,
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        if isinstance(error, app_commands.MissingPermissions):
            message = (
                "❌ Tu dois disposer de la permission "
                "**Gérer le serveur** pour lancer cette commande."
            )
        else:
            message = "❌ Une erreur inattendue est survenue."

        if interaction.response.is_done():
            await interaction.followup.send(
                message,
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                message,
                ephemeral=True,
            )


async def setup(bot: MadameRillionaBot) -> None:
    await bot.add_cog(CardAdminCog(bot))
