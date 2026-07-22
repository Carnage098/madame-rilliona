from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import card_embed, error_embed


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
        cards = await self.bot.card_repository.autocomplete(current)
        return [
            app_commands.Choice(
                name=card.display_name[:100],
                value=str(card.ygoprodeck_id),
            )
            for card in cards[:25]
        ]

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
