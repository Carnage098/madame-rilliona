from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from config import SETTINGS
from utils.embeds import card_embed, error_embed, success_embed


LOGGER = logging.getLogger(__name__)


class CardAdminCog(
    commands.GroupCog,
    group_name="base",
    group_description="Administration de la base",
):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="statut", description="Afficher l'état du catalogue de cartes")
    async def catalogue_status(self, interaction: discord.Interaction) -> None:
        count = await self.bot.card_repository.count()
        categories = await self.bot.card_repository.category_counts()
        category_lines = "\n".join(
            f"• **{name}** : {total}"
            for name, total in categories.items()
        ) or "• Aucune carte classée"
        discovery_status = (
            f"active, une découverte environ toutes les "
            f"{SETTINGS.random_discovery_interval_minutes} minutes"
            if SETTINGS.random_discovery_enabled
            else "désactivée"
        )
        description = (
            f"**{count}** carte(s) enregistrée(s).\n\n"
            f"**Classement**\n{category_lines}\n\n"
            f"**Découverte aléatoire** : {discovery_status}.\n"
            "Toute carte trouvée par `/carte rechercher` est enregistrée automatiquement."
        )
        await interaction.response.send_message(
            embed=success_embed("État du catalogue", description),
            ephemeral=True,
        )

    @app_commands.command(
        name="synchroniser_cartes",
        description="Synchroniser toutes les cartes depuis YGOPRODeck",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def synchronize_cards(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        if not interaction.permissions.manage_guild:
            await interaction.followup.send(
                embed=error_embed(
                    "Permission refusée",
                    "La permission Gérer le serveur est requise.",
                ),
                ephemeral=True,
            )
            return
        try:
            count = await self.bot.card_catalog_service.synchronize()
        except Exception as error:
            LOGGER.exception("Échec de la synchronisation complète")
            await interaction.followup.send(
                embed=error_embed("Synchronisation impossible", str(error)),
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            embed=success_embed(
                "Catalogue synchronisé",
                f"**{count}** cartes ont été ajoutées, classées ou mises à jour.",
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="decouvrir_aleatoire",
        description="Découvrir et enregistrer immédiatement une carte aléatoire",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def discover_random(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        if not interaction.permissions.manage_guild:
            await interaction.followup.send(
                embed=error_embed(
                    "Permission refusée",
                    "La permission Gérer le serveur est requise.",
                ),
                ephemeral=True,
            )
            return
        try:
            card = await self.bot.card_catalog_service.discover_random()
        except Exception:
            LOGGER.exception("Échec de la découverte aléatoire")
            await interaction.followup.send(
                embed=error_embed(
                    "Découverte impossible",
                    "La base externe n'a pas répondu correctement.",
                ),
                ephemeral=True,
            )
            return

        embed = card_embed(card)
        embed.title = f"🎲 {card.display_name}"
        embed.set_footer(
            text=(
                f"Carte découverte et enregistrée • ID YGOPRODeck : "
                f"{card.ygoprodeck_id}"
            )
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CardAdminCog(bot))
