from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from utils.embeds import archetype_embed, error_embed, success_embed


class ArchetypeCog(commands.GroupCog, group_name="archetype", group_description="Bibliothèque des archétypes"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def archetype_autocomplete(self, interaction: discord.Interaction, current: str):
        entries = await self.bot.archetype_repository.autocomplete(current)
        return [app_commands.Choice(name=item.name[:100], value=item.name) for item in entries[:25]]

    @app_commands.command(name="ajouter", description="Ajouter un archétype à la bibliothèque")
    @app_commands.default_permissions(manage_guild=True)
    async def add_archetype(
        self,
        interaction: discord.Interaction,
        nom: str,
        presentation: str,
        style_de_jeu: str,
        difficulte: str = "Intermédiaire",
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        if not interaction.permissions.manage_guild:
            await interaction.followup.send(embed=error_embed("Permission refusée", "La permission Gérer le serveur est requise."), ephemeral=True)
            return
        try:
            archetype = await self.bot.archetype_repository.create(
                name=nom,
                presentation=presentation,
                play_style=style_de_jeu,
                difficulty=difficulte,
                created_by=interaction.user.id,
            )
        except ValueError as error:
            await interaction.followup.send(embed=error_embed("Ajout impossible", str(error)), ephemeral=True)
            return
        await interaction.followup.send(
            embed=success_embed("Archétype ajouté", f"**{archetype.name}** est maintenant dans la bibliothèque."),
            ephemeral=True,
        )

    @app_commands.command(name="consulter", description="Consulter la fiche d'un archétype")
    @app_commands.autocomplete(nom=archetype_autocomplete)
    async def view_archetype(self, interaction: discord.Interaction, nom: str) -> None:
        archetype = await self.bot.archetype_repository.get_by_name(nom)
        if archetype is None:
            await interaction.response.send_message(embed=error_embed("Archétype introuvable", "Vérifie le nom demandé."), ephemeral=True)
            return
        await interaction.response.send_message(embed=archetype_embed(archetype))

    @app_commands.command(name="liste", description="Lister les archétypes archivés")
    async def list_archetypes(self, interaction: discord.Interaction) -> None:
        entries = await self.bot.archetype_repository.list_all()
        if not entries:
            await interaction.response.send_message(embed=error_embed("Bibliothèque vide", "Aucun archétype n'a encore été ajouté."), ephemeral=True)
            return
        lines = [f"• **{item.name}** — {item.combo_count} combo(s) — {item.difficulty}" for item in entries]
        embed = discord.Embed(title="📚 Archétypes", description="\n".join(lines)[:4000], colour=discord.Colour.purple())
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ArchetypeCog(bot))
