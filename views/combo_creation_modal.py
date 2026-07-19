from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

from services.errors import MadameRillionaError
from utils.combo_embeds import build_combo_embed
from views.combo_view import ComboView

if TYPE_CHECKING:
    from bot import MadameRillionaBot


class ComboCreationModal(
    discord.ui.Modal,
    title="Archiver une nouvelle ligne de combo",
):
    description = discord.ui.TextInput(
        label="Présentation du combo",
        placeholder=(
            "Explique l'objectif de cette ligne, son contexte "
            "et ce qu'elle cherche à accomplir."
        ),
        style=discord.TextStyle.paragraph,
        min_length=10,
        max_length=1200,
        required=True,
    )

    steps = discord.ui.TextInput(
        label="Étapes — une action par ligne",
        placeholder=(
            "1. Invoquez...\n"
            "2. Activez l'effet de...\n"
            "3. Ajoutez..."
        ),
        style=discord.TextStyle.paragraph,
        min_length=10,
        max_length=4000,
        required=True,
    )

    endboard = discord.ui.TextInput(
        label="Terrain final",
        placeholder=(
            "Listez les monstres, Magies/Pièges, interactions "
            "et ressources présentes à la fin."
        ),
        style=discord.TextStyle.paragraph,
        min_length=3,
        max_length=1200,
        required=True,
    )

    interruptions = discord.ui.TextInput(
        label="Interactions produites",
        placeholder=(
            "Négations, destructions, bannissements, interruptions "
            "rapides, floodgates..."
        ),
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=False,
    )

    analysis = discord.ui.TextInput(
        label="Analyse : faiblesses, choke points, recovery",
        placeholder=(
            "Faiblesses : ...\n"
            "Choke points : ...\n"
            "Recovery : ..."
        ),
        style=discord.TextStyle.paragraph,
        max_length=1800,
        required=False,
    )

    def __init__(
        self,
        *,
        bot: MadameRillionaBot,
        archetype: str,
        name: str,
        combo_type: str,
        game_format: str,
        banlist: str | None,
        difficulty: str,
        starter_text: str,
        requirements: str | None,
        follow_up: str | None,
        video_url: str | None,
    ) -> None:
        super().__init__(timeout=900)
        self.bot = bot
        self.archetype = archetype
        self.combo_name = name
        self.combo_type = combo_type
        self.game_format = game_format
        self.banlist = banlist
        self.difficulty = difficulty
        self.starter_text = starter_text
        self.requirements = requirements
        self.follow_up = follow_up
        self.video_url = video_url

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ) -> None:
        await interaction.response.defer(
            thinking=True,
            ephemeral=True,
        )

        try:
            combo = await self.bot.combo_service.create_combo(
                archetype_query=self.archetype,
                name=self.combo_name,
                description=str(self.description),
                combo_type=self.combo_type,
                game_format=self.game_format,
                banlist=self.banlist,
                difficulty=self.difficulty,
                starter_text=self.starter_text,
                requirements=self.requirements,
                steps_text=str(self.steps),
                endboard=str(self.endboard),
                interruptions=str(self.interruptions),
                follow_up=self.follow_up,
                analysis_text=str(self.analysis),
                video_url=self.video_url,
                author_id=interaction.user.id,
            )
        except MadameRillionaError as exc:
            await interaction.edit_original_response(
                content=f"❌ {exc}",
            )
            return
        except Exception:
            logging.exception("Erreur pendant la création d'un combo.")
            await interaction.edit_original_response(
                content=(
                    "❌ Une erreur inattendue a empêché "
                    "l'enregistrement du combo."
                ),
            )
            return

        await interaction.edit_original_response(
            content="✅ Le combo a été ajouté à la bibliothèque.",
            embed=build_combo_embed(combo),
            view=ComboView(combo),
        )
