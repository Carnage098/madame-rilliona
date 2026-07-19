from __future__ import annotations

import logging

import aiohttp
import discord
from discord.ext import commands

from config import Settings
from database import Database
from repositories.archetype_repository import ArchetypeRepository
from repositories.card_repository import CardRepository
from repositories.combo_repository import ComboRepository
from services.card_api_service import CardApiService
from services.card_catalog_service import CardCatalogService
from services.card_image_service import CardImageService
from services.combo_service import ComboService


COGS = (
    "cogs.cards",
    "cogs.card_admin",
    "cogs.archetypes",
    "cogs.combos",
)


class MadameRillionaBot(commands.Bot):
    """Bot principal de Madame Rilliona."""

    settings: Settings
    database: Database
    http_session: aiohttp.ClientSession

    card_repository: CardRepository
    card_api: CardApiService
    card_catalog: CardCatalogService
    card_images: CardImageService

    archetype_repository: ArchetypeRepository
    combo_repository: ComboRepository
    combo_service: ComboService

    def __init__(self, settings: Settings) -> None:
        intents = discord.Intents.default()

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )
        self.settings = settings

    async def setup_hook(self) -> None:
        self.database = Database(self.settings.database_url)
        await self.database.connect()
        await self.database.initialize_schema()

        timeout = aiohttp.ClientTimeout(total=180, connect=30)
        self.http_session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                "User-Agent": (
                    "Madame-Rilliona-Discord-Bot/2.0 "
                    "(Yu-Gi-Oh card and combo library)"
                )
            },
        )

        self.card_repository = CardRepository(self.database)
        self.card_api = CardApiService(self.http_session)
        self.card_catalog = CardCatalogService(
            repository=self.card_repository,
            api=self.card_api,
        )
        self.card_images = CardImageService(
            session=self.http_session,
            image_directory=self.settings.card_image_directory,
        )

        self.archetype_repository = ArchetypeRepository(self.database)
        self.combo_repository = ComboRepository(self.database)
        self.combo_service = ComboService(
            archetypes=self.archetype_repository,
            combos=self.combo_repository,
        )

        for extension in COGS:
            await self.load_extension(extension)
            logging.info("Cog chargé : %s", extension)

        if self.settings.guild_id:
            guild = discord.Object(id=self.settings.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            logging.info(
                "%s commandes synchronisées sur le serveur de développement.",
                len(synced),
            )
        else:
            synced = await self.tree.sync()
            logging.info("%s commandes globales synchronisées.", len(synced))

    async def close(self) -> None:
        if hasattr(self, "http_session") and not self.http_session.closed:
            await self.http_session.close()

        if hasattr(self, "database"):
            await self.database.close()

        await super().close()

    async def on_ready(self) -> None:
        if self.user is None:
            return

        logging.info(
            "Madame Rilliona connectée : %s (%s)",
            self.user,
            self.user.id,
        )


def main() -> None:
    settings = Settings.from_environment()

    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    )

    bot = MadameRillionaBot(settings)
    bot.run(settings.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
