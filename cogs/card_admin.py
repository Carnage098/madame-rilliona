from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import error_embed, success_embed


class CardAdminCog(commands.GroupCog, group_name="base", group_description="Administration de la base"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="synchroniser_cartes", description="Synchroniser les cartes depuis YGOPRODeck")
    @app_commands.default_permissions(manage_guild=True)
    async def synchronize_cards(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)
        if not interaction.permissions.manage_guild:
            await interaction.followup.send(
                embed=error_embed("Permission refusée", "La permission Gérer le serveur est requise."),
                ephemeral=True,
            )
            return
        try:
            count = await self.bot.card_catalog_service.synchronize()
        except Exception as error:
            await interaction.followup.send(
                embed=error_embed("Synchronisation impossible", str(error)),
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            embed=success_embed("Catalogue synchronisé", f"**{count}** cartes ont été ajoutées ou mises à jour."),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CardAdminCog(bot))
