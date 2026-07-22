from __future__ import annotations

import logging

import aiohttp
import discord
from discord.ext import commands

from config import SETTINGS
from database_manager import Database
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
    """Bot principal, compatible avec les architectures V2.2 à V2.5."""

    def __init__(self) -> None:
        super().__init__(
            command_prefix="!",
            intents=discord.Intents.default(),
            help_command=None,
        )

        self.database = Database(SETTINGS.database_url)
        self.http_session: aiohttp.ClientSession | None = None

        self.card_repository: CardRepository | None = None
        self.archetype_repository: ArchetypeRepository | None = None
        self.combo_repository: ComboRepository | None = None

        self.card_api_service: CardApiService | None = None
        self.card_catalog_service: CardCatalogService | None = None
        self.card_image_service: CardImageService | None = None
        self.combo_service: ComboService | None = None

        # Anciens noms d'attributs initialisés pour les vieux cogs.
        self.card_api: CardApiService | None = None
        self.card_catalog: CardCatalogService | None = None
        self.card_images: CardImageService | None = None

    async def setup_hook(self) -> None:
        await self.database.connect()
        await self.database.initialize_schema()
        pool = self.database.require_pool()
        logging.getLogger(__name__).info(
            "Connexion PostgreSQL établie et schéma vérifié."
        )

        self.http_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=180, connect=30),
            headers={
                "User-Agent": (
                    "Madame-Rilliona-Discord-Bot/2.5 "
                    "(Yu-Gi-Oh card and combo library)"
                )
            },
        )

        self.card_repository = CardRepository(pool)
        self.archetype_repository = ArchetypeRepository(pool)
        self.combo_repository = ComboRepository(pool)

        self.card_api_service = CardApiService()
        self.card_catalog_service = CardCatalogService(
            api=self.card_api_service,
            repository=self.card_repository,
        )
        self.card_image_service = CardImageService(
            SETTINGS.card_image_directory
        )
        self.combo_service = ComboService(
            archetypes=self.archetype_repository,
            combos=self.combo_repository,
        )

        # Alias exigés par certaines versions précédentes des cogs.
        self.card_api = self.card_api_service
        self.card_catalog = self.card_catalog_service
        self.card_images = self.card_image_service

        for extension in COGS:
            await self.load_extension(extension)
            logging.getLogger(__name__).info(
                "Cog chargé : %s",
                extension,
            )

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
            logging.getLogger(__name__).info(
                "%s commande(s) globale(s) synchronisée(s).",
                len(synced),
            )

    async def on_ready(self) -> None:
        if self.user is None:
            return

        logging.getLogger(__name__).info(
            "Madame Rilliona connectée en tant que %s (%s).",
            self.user,
            self.user.id,
        )

        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="les archives de combos",
            )
        )

    async def close(self) -> None:
        if self.http_session is not None and not self.http_session.closed:
            await self.http_session.close()
        self.http_session = None

        await self.database.close()
        await super().close()


def main() -> None:
    logging.basicConfig(
        level=getattr(logging, SETTINGS.log_level.upper(), logging.INFO),
        format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    )

    bot = MadameRillionaBot()
    bot.run(SETTINGS.discord_token, log_handler=None)


if __name__ == "__main__":
    main()
