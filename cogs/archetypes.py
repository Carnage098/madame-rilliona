from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import archetype_embed, error_embed, success_embed


LOGGER = logging.getLogger(__name__)


class ArchetypeCog(
    commands.GroupCog,
    group_name="archetype",
    group_description="Bibliothèque des archétypes",
):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def archetype_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ):
        entries = await self.bot.archetype_repository.autocomplete(current)
        return [
            app_commands.Choice(name=item.name[:100], value=item.name)
            for item in entries[:25]
        ]

    @app_commands.command(
        name="ajouter",
        description="Ajouter un archétype et importer automatiquement toutes ses cartes",
    )
    @app_commands.default_permissions(manage_guild=True)
    async def add_archetype(
        self,
        interaction: discord.Interaction,
        nom: str,
        presentation: str,
        style_de_jeu: str,
        difficulte: str = "Intermédiaire",
    ) -> None:
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
            sync = await self.bot.card_catalog_service.synchronize_archetype(nom)
            archetype = await self.bot.archetype_repository.create(
                name=nom,
                api_name=sync.canonical_name,
                presentation=presentation,
                play_style=style_de_jeu,
                difficulty=difficulte,
                created_by=interaction.user.id,
            )
        except ValueError as error:
            await interaction.followup.send(
                embed=error_embed("Ajout impossible", str(error)),
                ephemeral=True,
            )
            return
        except Exception:
            LOGGER.exception("Échec de l'ajout et de la synchronisation de %r", nom)
            await interaction.followup.send(
                embed=error_embed(
                    "Synchronisation impossible",
                    "La base externe n'a pas répondu correctement. Réessaie dans quelques instants.",
                ),
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            embed=success_embed(
                "Archétype ajouté",
                (
                    f"**{archetype.name}** est maintenant dans la bibliothèque.\n"
                    f"Nom reconnu par la base : **{sync.canonical_name}**\n"
                    f"Cartes enregistrées et classées : **{sync.imported_count}**"
                ),
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="synchroniser",
        description="Réimporter et mettre à jour toutes les cartes d'un archétype",
    )
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.autocomplete(nom=archetype_autocomplete)
    async def synchronize_archetype(
        self,
        interaction: discord.Interaction,
        nom: str,
    ) -> None:
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

        entry = await self.bot.archetype_repository.get_by_name(nom)
        requested_name = entry.catalogue_name if entry else nom
        try:
            sync = await self.bot.card_catalog_service.synchronize_archetype(
                requested_name
            )
            if entry is not None:
                await self.bot.archetype_repository.mark_cards_synced(
                    entry.id,
                    api_name=sync.canonical_name,
                )
        except ValueError as error:
            await interaction.followup.send(
                embed=error_embed("Synchronisation impossible", str(error)),
                ephemeral=True,
            )
            return
        except Exception:
            LOGGER.exception("Échec de la synchronisation de %r", requested_name)
            await interaction.followup.send(
                embed=error_embed(
                    "Synchronisation impossible",
                    "La base externe n'a pas répondu correctement.",
                ),
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            embed=success_embed(
                "Archétype synchronisé",
                (
                    f"**{sync.canonical_name}** : "
                    f"**{sync.imported_count}** carte(s) ajoutée(s) ou mise(s) à jour."
                ),
            ),
            ephemeral=True,
        )

    @app_commands.command(name="consulter", description="Consulter la fiche d'un archétype")
    @app_commands.autocomplete(nom=archetype_autocomplete)
    async def view_archetype(
        self,
        interaction: discord.Interaction,
        nom: str,
    ) -> None:
        archetype = await self.bot.archetype_repository.get_by_name(nom)
        if archetype is None:
            await interaction.response.send_message(
                embed=error_embed(
                    "Archétype introuvable",
                    "Vérifie le nom demandé.",
                ),
                ephemeral=True,
            )
            return
        await interaction.response.send_message(embed=archetype_embed(archetype))

    @app_commands.command(name="liste", description="Lister les archétypes archivés")
    async def list_archetypes(self, interaction: discord.Interaction) -> None:
        entries = await self.bot.archetype_repository.list_all()
        if not entries:
            await interaction.response.send_message(
                embed=error_embed(
                    "Bibliothèque vide",
                    "Aucun archétype n'a encore été ajouté.",
                ),
                ephemeral=True,
            )
            return
        lines = [
            (
                f"• **{item.name}** — {item.card_count} carte(s) — "
                f"{item.combo_count} combo(s) — {item.difficulty}"
            )
            for item in entries
        ]
        embed = discord.Embed(
            title="📚 Archétypes",
            description="\n".join(lines)[:4000],
            colour=discord.Colour.purple(),
        )
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ArchetypeCog(bot))
