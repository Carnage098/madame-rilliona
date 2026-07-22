from __future__ import annotations

import discord
from discord import app_commands
from discord.ext import commands

from models.combo import Combo
from utils.embeds import combo_embed, error_embed, success_embed
from utils.text import parse_analysis, parse_steps, truncate


class ComboView(discord.ui.View):
    def __init__(self, combo: Combo) -> None:
        super().__init__(timeout=300)
        self.combo = combo
        if combo.video_url:
            self.add_item(discord.ui.Button(label="Voir la vidéo", url=combo.video_url, emoji="🎬"))

    @discord.ui.button(label="Étapes", style=discord.ButtonStyle.primary, emoji="🪜")
    async def steps(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        text = "\n".join(f"**{index}.** {step}" for index, step in enumerate(self.combo.steps, start=1))
        embed = discord.Embed(title=f"🪜 Étapes — {self.combo.name}", description=truncate(text, 4000), colour=discord.Colour.blurple())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Analyse", style=discord.ButtonStyle.secondary, emoji="🔎")
    async def analysis(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        embed = discord.Embed(title=f"🔎 Analyse — {self.combo.name}", colour=discord.Colour.orange())
        embed.add_field(name="Faiblesses", value=truncate(self.combo.weaknesses, 1024), inline=False)
        embed.add_field(name="Choke points", value=truncate(self.combo.choke_points, 1024), inline=False)
        embed.add_field(name="Recovery", value=truncate(self.combo.recovery, 1024), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Ressources", style=discord.ButtonStyle.success, emoji="🧰")
    async def resources(self, interaction: discord.Interaction, button: discord.ui.Button) -> None:
        embed = discord.Embed(title=f"🧰 Ressources — {self.combo.name}", colour=discord.Colour.green())
        embed.add_field(name="Starter", value=truncate(self.combo.starter, 1024), inline=False)
        embed.add_field(name="Prérequis", value=truncate(self.combo.prerequisites, 1024), inline=False)
        embed.add_field(name="Terrain final", value=truncate(self.combo.endboard, 1024), inline=False)
        embed.add_field(name="Interactions", value=truncate(self.combo.interactions, 1024), inline=False)
        embed.add_field(name="Follow-up", value=truncate(self.combo.follow_up, 1024), inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)


class ComboModal(discord.ui.Modal, title="Archiver le combo"):
    description_input = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, max_length=1500)
    steps_input = discord.ui.TextInput(label="Étapes — une action par ligne", style=discord.TextStyle.paragraph, max_length=4000)
    endboard_input = discord.ui.TextInput(label="Terrain final et interactions", style=discord.TextStyle.paragraph, max_length=1500)
    follow_up_input = discord.ui.TextInput(label="Follow-up", style=discord.TextStyle.paragraph, max_length=1000, required=False)
    analysis_input = discord.ui.TextInput(label="Faiblesses / Choke points / Recovery", style=discord.TextStyle.paragraph, max_length=2000)

    def __init__(self, cog: "ComboCog", payload: dict[str, object]) -> None:
        super().__init__()
        self.cog = cog
        self.payload = payload

    async def on_submit(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        endboard_text = self.endboard_input.value
        if "Interactions:" in endboard_text:
            endboard, interactions = endboard_text.split("Interactions:", 1)
        else:
            endboard, interactions = endboard_text, ""
        weaknesses, choke_points, recovery = parse_analysis(self.analysis_input.value)
        try:
            combo = await self.cog.bot.combo_repository.create(
                **self.payload,
                description=self.description_input.value,
                steps=parse_steps(self.steps_input.value),
                endboard=endboard,
                interactions=interactions,
                follow_up=self.follow_up_input.value,
                weaknesses=weaknesses,
                choke_points=choke_points,
                recovery=recovery,
                created_by=interaction.user.id,
            )
        except (ValueError, RuntimeError) as error:
            await interaction.followup.send(embed=error_embed("Création impossible", str(error)), ephemeral=True)
            return
        await interaction.followup.send(
            embed=success_embed("Combo archivé", f"**{combo.name}** a été ajouté à **{combo.archetype_name}**."),
            ephemeral=True,
        )


class ComboCog(commands.GroupCog, group_name="combo", group_description="Bibliothèque des combos"):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def archetype_autocomplete(self, interaction: discord.Interaction, current: str):
        entries = await self.bot.archetype_repository.autocomplete(current)
        return [app_commands.Choice(name=item.name[:100], value=item.name) for item in entries[:25]]

    async def combo_autocomplete(self, interaction: discord.Interaction, current: str):
        entries = await self.bot.combo_repository.autocomplete(current)
        return [
            app_commands.Choice(name=f"{item.name} — {item.archetype_name}"[:100], value=str(item.id))
            for item in entries[:25]
        ]

    @app_commands.command(name="ajouter", description="Ajouter un combo structuré")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.autocomplete(archetype=archetype_autocomplete)
    async def add_combo(
        self,
        interaction: discord.Interaction,
        archetype: str,
        nom: str,
        starter: str,
        prerequis: str = "Aucun",
        format: str = "TCG",
        banlist: str = "",
        difficulte: str = "Intermédiaire",
        type_de_ligne: str = "Standard",
        video: str | None = None,
    ) -> None:
        if not interaction.permissions.manage_guild:
            await interaction.response.send_message(embed=error_embed("Permission refusée", "La permission Gérer le serveur est requise."), ephemeral=True)
            return
        archetype_entry = await self.bot.archetype_repository.get_by_name(archetype)
        if archetype_entry is None:
            await interaction.response.send_message(embed=error_embed("Archétype introuvable", "Ajoute d'abord l'archétype avec `/archetype ajouter`."), ephemeral=True)
            return
        payload: dict[str, object] = {
            "archetype_id": archetype_entry.id,
            "name": nom,
            "game_format": format,
            "banlist": banlist,
            "difficulty": difficulte,
            "line_type": type_de_ligne,
            "starter": starter,
            "prerequisites": prerequis,
            "video_url": video,
        }
        await interaction.response.send_modal(ComboModal(self, payload))

    @app_commands.command(name="consulter", description="Consulter un combo")
    @app_commands.autocomplete(combo=combo_autocomplete)
    async def view_combo(self, interaction: discord.Interaction, combo: str) -> None:
        entry = await self.bot.combo_repository.get_by_id(int(combo)) if combo.isdigit() else await self.bot.combo_repository.get_by_name(combo)
        if entry is None:
            await interaction.response.send_message(embed=error_embed("Combo introuvable", "Vérifie le combo demandé."), ephemeral=True)
            return
        await interaction.response.send_message(embed=combo_embed(entry), view=ComboView(entry))

    @app_commands.command(name="liste", description="Lister les combos archivés")
    @app_commands.autocomplete(archetype=archetype_autocomplete)
    async def list_combos(self, interaction: discord.Interaction, archetype: str | None = None) -> None:
        entries = await self.bot.combo_repository.list_all(archetype_name=archetype)
        if not entries:
            await interaction.response.send_message(embed=error_embed("Aucun combo", "Aucun combo ne correspond à cette recherche."), ephemeral=True)
            return
        lines = [f"• **{item.name}** — {item.archetype_name} — `{item.game_format}` — ID `{item.id}`" for item in entries]
        embed = discord.Embed(title="🧠 Combos archivés", description="\n".join(lines)[:4000], colour=discord.Colour.purple())
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="supprimer", description="Supprimer un combo")
    @app_commands.default_permissions(manage_guild=True)
    @app_commands.autocomplete(combo=combo_autocomplete)
    async def delete_combo(self, interaction: discord.Interaction, combo: str) -> None:
        if not interaction.permissions.manage_guild:
            await interaction.response.send_message(embed=error_embed("Permission refusée", "La permission Gérer le serveur est requise."), ephemeral=True)
            return
        if not combo.isdigit():
            entry = await self.bot.combo_repository.get_by_name(combo)
            combo_id = entry.id if entry else 0
        else:
            combo_id = int(combo)
        deleted = await self.bot.combo_repository.delete(combo_id)
        if not deleted:
            await interaction.response.send_message(embed=error_embed("Combo introuvable", "Aucun combo n'a été supprimé."), ephemeral=True)
            return
        await interaction.response.send_message(embed=success_embed("Combo supprimé", f"Le combo `{combo_id}` a été supprimé."), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ComboCog(bot))
