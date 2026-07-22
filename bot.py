import logging

import discord
from discord.ext import commands

from config import SETTINGS
from db_connection import Database
from repositories.archetype_repository import ArchetypeRepository
from repositories.card_repository import CardRepository
from repositories.combo_repository import ComboRepository
from services.card_api_service import CardApiService
from services.card_catalog_service import CardCatalogService
from services.card_image_service import CardImageService


COGS = (
    "cogs.cards",
    "cogs.card_admin",
    "cogs.archetypes",
    "cogs.combos",
)


class MadameRillionaBot(commands.Bot):
    def __init__(self) -> None:
        super().__init__(command_prefix="!", intents=discord.Intents.default())
        self.database = Database(SETTINGS.database_url)

    async def setup_hook(self) -> None:
        await self.database.connect()
        await self.database.initialize()
        pool = self.database.require_pool()

        self.card_repository = CardRepository(pool)
        self.archetype_repository = ArchetypeRepository(pool)
        self.combo_repository = ComboRepository(pool)

        self.card_api_service = CardApiService()
        self.card_catalog_service = CardCatalogService(
            self.card_api_service,
            self.card_repository,
        )
        self.card_image_service = CardImageService(SETTINGS.card_image_directory)

        for extension in COGS:
            await self.load_extension(extension)
            logging.getLogger(__name__).info("Cog chargé : %s", extension)

        if SETTINGS.guild_id is not None:
            guild = discord.Object(id=SETTINGS.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logging.getLogger(__name__).info(
                "%s commande(s) synchronisée(s) sur le serveur configuré.",
                len(synced),
            )
        else:
            synced = await self.tree.sync()
            logging.getLogger(__name__).info("%s commande(s) globale(s) synchronisée(s).", len(synced))

    async def close(self) -> None:
        await self.database.close()
        await super().close()


bot = MadameRillionaBot()


@bot.event
async def on_ready() -> None:
    logging.getLogger(__name__).info("Madame Rilliona connectée en tant que %s.", bot.user)


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, SETTINGS.log_level, logging.INFO),
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    )
    bot.run(SETTINGS.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
