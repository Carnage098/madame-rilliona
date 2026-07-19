from __future__ import annotations

from typing import TYPE_CHECKING

import discord

from services.errors import MadameRillionaError

if TYPE_CHECKING:
    from bot import MadameRillionaBot


class DeleteComboConfirmationView(discord.ui.View):
    def __init__(
        self,
        *,
        bot: MadameRillionaBot,
        combo_id: int,
        combo_name: str,
        requester_id: int,
    ) -> None:
        super().__init__(timeout=60)
        self.bot = bot
        self.combo_id = combo_id
        self.combo_name = combo_name
        self.requester_id = requester_id

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if interaction.user.id == self.requester_id:
            return True

        await interaction.response.send_message(
            "❌ Seule la personne ayant lancé la commande peut confirmer.",
            ephemeral=True,
        )
        return False

    @discord.ui.button(
        label="Supprimer définitivement",
        emoji="🗑️",
        style=discord.ButtonStyle.danger,
    )
    async def confirm(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        try:
            await self.bot.combo_service.delete_combo(self.combo_id)
        except MadameRillionaError as exc:
            await interaction.response.edit_message(
                content=f"❌ {exc}",
                embed=None,
                view=None,
            )
            return

        await interaction.response.edit_message(
            content=(
                f"✅ Le combo **{self.combo_name}** "
                "a été supprimé de la bibliothèque."
            ),
            embed=None,
            view=None,
        )
        self.stop()

    @discord.ui.button(
        label="Annuler",
        style=discord.ButtonStyle.secondary,
    )
    async def cancel(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.edit_message(
            content="Suppression annulée.",
            embed=None,
            view=None,
        )
        self.stop()
