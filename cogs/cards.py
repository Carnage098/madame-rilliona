from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from bot import MadameRillionaBot
from services.card_api_service import CardApiError
from utils.embeds import build_card_embed
from utils.text import truncate


class CardsCog(
    commands.GroupCog,
    group_name="carte",
    group_description="Consulter le catalogue de cartes Yu-Gi-Oh!.",
):
    def __init__(self, bot: MadameRillionaBot) -> None:
        self.bot = bot

    @app_commands.command(
        name="rechercher",
        description="Affiche la fiche complète d'une carte Yu-Gi-Oh!.",
    )
    @app_commands.describe(
        nom="Nom français ou anglais de la carte."
    )
    async def rechercher(
        self,
        interaction: discord.Interaction,
        nom: str,
    ) -> None:
        await interaction.response.defer(thinking=True)

        try:
            card = await self.bot.card_catalog.find_card(nom)
        except CardApiError:
            await interaction.edit_original_response(
                content=(
                    "❌ La carte n'est pas disponible dans le catalogue local "
                    "et l'API YGOPRODeck ne répond pas actuellement."
                )
            )
            return

        if card is None:
            await interaction.edit_original_response(
                content=f"🔎 Aucune carte trouvée pour **{nom}**."
            )
            return

        embed = build_card_embed(card)

        image_path = await self.bot.card_images.get_cached_image(
            card.ygoprodeck_id,
            card.image_small_url or card.image_url,
        )

        if image_path is not None:
            filename = f"card_{card.ygoprodeck_id}{image_path.suffix}"
            file = discord.File(image_path, filename=filename)
            embed.set_image(url=f"attachment://{filename}")
            await interaction.edit_original_response(
                content=None,
                embed=embed,
                attachments=[file],
            )
            return

        await interaction.edit_original_response(
            content=None,
            embed=embed,
        )

    @rechercher.autocomplete("nom")
    async def rechercher_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        cards = await self.bot.card_repository.autocomplete(
            current,
            limit=25,
        )
        return [
            app_commands.Choice(
                name=truncate(card.display_name, 100),
                value=card.display_name,
            )
            for card in cards
        ]

    @app_commands.command(
        name="archetype",
        description="Liste les cartes associées à un archétype.",
    )
    @app_commands.describe(
        nom="Nom de l'archétype, par exemple Maliss ou Livre de Magie.",
    )
    async def archetype(
        self,
        interaction: discord.Interaction,
        nom: str,
    ) -> None:
        await interaction.response.defer(thinking=True)

        cards = await self.bot.card_repository.find_by_archetype(
            nom,
            limit=50,
        )

        if not cards:
            await interaction.edit_original_response(
                content=(
                    f"🔎 Aucune carte locale trouvée pour l'archétype "
                    f"**{nom}**. Lance d'abord `/base synchroniser_cartes`."
                )
            )
            return

        shown = cards[:25]
        lines = [
            f"• **{card.display_name}** — {card.display_type}"
            for card in shown
        ]

        embed = discord.Embed(
            title=f"Archétype : {nom}",
            description="\n".join(lines),
            colour=discord.Colour.from_rgb(112, 84, 190),
        )
        embed.set_footer(
            text=(
                f"{len(cards)} carte(s) trouvée(s)"
                + (
                    " • Les 25 premières sont affichées."
                    if len(cards) > 25
                    else ""
                )
            )
        )

        await interaction.edit_original_response(embed=embed)


async def setup(bot: MadameRillionaBot) -> None:
    await bot.add_cog(CardsCog(bot))
