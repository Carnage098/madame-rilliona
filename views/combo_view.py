from __future__ import annotations

import discord

from models.combo import ComboRecord
from utils.combo_embeds import (
    build_analysis_embed,
    build_resources_embed,
    build_steps_embed,
)


class ComboStepsView(discord.ui.View):
    def __init__(
        self,
        *,
        combo: ComboRecord,
        requester_id: int,
    ) -> None:
        super().__init__(timeout=600)
        self.combo = combo
        self.requester_id = requester_id
        self.index = 0
        self._refresh_buttons()

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if interaction.user.id == self.requester_id:
            return True

        await interaction.response.send_message(
            "❌ Cette navigation appartient à un autre utilisateur.",
            ephemeral=True,
        )
        return False

    def _refresh_buttons(self) -> None:
        self.previous.disabled = self.index <= 0
        self.next.disabled = self.index >= len(self.combo.steps) - 1

    @discord.ui.button(
        label="Précédente",
        emoji="◀️",
        style=discord.ButtonStyle.secondary,
    )
    async def previous(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.index = max(0, self.index - 1)
        self._refresh_buttons()
        await interaction.response.edit_message(
            embed=build_steps_embed(self.combo, self.index),
            view=self,
        )

    @discord.ui.button(
        label="Suivante",
        emoji="▶️",
        style=discord.ButtonStyle.primary,
    )
    async def next(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self.index = min(len(self.combo.steps) - 1, self.index + 1)
        self._refresh_buttons()
        await interaction.response.edit_message(
            embed=build_steps_embed(self.combo, self.index),
            view=self,
        )


class ComboView(discord.ui.View):
    def __init__(self, combo: ComboRecord) -> None:
        super().__init__(timeout=900)
        self.combo = combo

        if combo.video_url:
            self.add_item(
                discord.ui.Button(
                    label="Voir la vidéo",
                    emoji="🎥",
                    style=discord.ButtonStyle.link,
                    url=combo.video_url,
                )
            )

    @discord.ui.button(
        label="Étapes",
        emoji="📑",
        style=discord.ButtonStyle.primary,
    )
    async def steps(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if not self.combo.steps:
            await interaction.response.send_message(
                "Aucune étape n'est enregistrée.",
                ephemeral=True,
            )
            return

        view = ComboStepsView(
            combo=self.combo,
            requester_id=interaction.user.id,
        )
        await interaction.response.send_message(
            embed=build_steps_embed(self.combo, 0),
            view=view,
            ephemeral=True,
        )

    @discord.ui.button(
        label="Analyse",
        emoji="🔍",
        style=discord.ButtonStyle.secondary,
    )
    async def analysis(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.send_message(
            embed=build_analysis_embed(self.combo),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Ressources",
        emoji="🗂️",
        style=discord.ButtonStyle.secondary,
    )
    async def resources(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.send_message(
            embed=build_resources_embed(self.combo),
            ephemeral=True,
        )
