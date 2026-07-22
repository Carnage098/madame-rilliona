from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import card_embed, error_embed


class CardCog(commands.GroupCog, group_name="carte", group_description="Consulter le catalogue de cartes"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def card_autocomplete(self, interaction: discord.Interaction, current: str):
        cards = await self.bot.card_repository.autocomplete(current)
        return [
            app_commands.Choice(name=card.display_name[:100], value=str(card.ygoprodeck_id))
            for card in cards[:25]
        ]

    @app_commands.command(name="rechercher", description="Rechercher une carte Yu-Gi-Oh!")
    @app_commands.describe(carte="Commence à saisir le nom de la carte")
    @app_commands.autocomplete(carte=card_autocomplete)
    async def search_card(self, interaction: discord.Interaction, carte: str) -> None:
        await interaction.response.defer()
        card = None
        if carte.isdigit():
            card = await self.bot.card_repository.get_by_id(int(carte))
        if card is None:
            results = await self.bot.card_repository.search(carte, limit=1)
            card = results[0] if results else None
        if card is None:
            await interaction.followup.send(
                embed=error_embed("Carte introuvable", "Synchronise d'abord le catalogue avec `/base synchroniser_cartes`."),
                ephemeral=True,
            )
            return

        embed = card_embed(card)
        try:
            image_path = await self.bot.card_image_service.get(card)
        except Exception:
            image_path = None
        if image_path:
            file = discord.File(image_path, filename=image_path.name)
            embed.set_image(url=f"attachment://{image_path.name}")
            await interaction.followup.send(embed=embed, file=file)
        else:
            if card.image_url:
                embed.set_image(url=card.image_url)
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="archetype", description="Lister les cartes d'un archétype")
    async def cards_by_archetype(self, interaction: discord.Interaction, nom: str) -> None:
        await interaction.response.defer()
        cards = await self.bot.card_repository.list_by_archetype(nom)
        if not cards:
            await interaction.followup.send(
                embed=error_embed("Aucune carte", "Aucune carte ne correspond à cet archétype."),
                ephemeral=True,
            )
            return
        lines = [f"• **{card.display_name}** (`{card.ygoprodeck_id}`)" for card in cards]
        embed = discord.Embed(
            title=f"🎴 Cartes — {nom}",
            description="\n".join(lines)[:4000],
            colour=discord.Colour.purple(),
        )
        embed.set_footer(text=f"{len(cards)} carte(s) affichée(s)")
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CardCog(bot))
