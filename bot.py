from __future__ import annotations

import asyncio
import contextlib
import logging
import random

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
from services.card_import_service import CardImportService
from services.combo_service import ComboService


LOGGER = logging.getLogger(__name__)

COGS = (
    "cogs.cards",
    "cogs.card_admin",
    "cogs.archetypes",
    "cogs.combos",
)


class MadameRillionaBot(commands.Bot):
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
        self.card_import_service: CardImportService | None = None
        self.combo_service: ComboService | None = None

        self.card_api: CardApiService | None = None
        self.card_catalog: CardCatalogService | None = None
        self.card_images: CardImageService | None = None
        self.card_imports: CardImportService | None = None

        self._random_discovery_task: asyncio.Task[None] | None = None

    async def setup_hook(self) -> None:
        await self.database.connect()
        await self.database.initialize_schema()
        pool = self.database.require_pool()
        LOGGER.info("Connexion PostgreSQL établie et schéma vérifié.")

        self.http_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=180, connect=30),
            headers={
                "User-Agent": (
                    "Madame-Rilliona-Discord-Bot/2.9 "
                    "(Yu-Gi-Oh card, archetype and combo library)"
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
        self.card_import_service = CardImportService(
            catalog=self.card_catalog_service,
            repository=self.card_repository,
            images=self.card_image_service,
            max_image_bytes=SETTINGS.max_staff_image_bytes,
        )
        self.combo_service = ComboService(
            archetypes=self.archetype_repository,
            combos=self.combo_repository,
        )

        self.card_api = self.card_api_service
        self.card_catalog = self.card_catalog_service
        self.card_images = self.card_image_service
        self.card_imports = self.card_import_service

        for extension in COGS:
            await self.load_extension(extension)
            LOGGER.info("Cog chargé : %s", extension)

        if SETTINGS.guild_id is not None:
            guild = discord.Object(id=SETTINGS.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)
            LOGGER.info(
                "%s commande(s) synchronisée(s) sur le serveur configuré.",
                len(synced),
            )
        else:
            synced = await self.tree.sync()
            LOGGER.info("%s commande(s) globale(s) synchronisée(s).", len(synced))

        if SETTINGS.random_discovery_enabled:
            self._random_discovery_task = asyncio.create_task(
                self._random_discovery_loop(),
                name="madame-rilliona-random-card-discovery",
            )
            LOGGER.info(
                "Découverte aléatoire activée : intervalle de base %s minute(s).",
                SETTINGS.random_discovery_interval_minutes,
            )

    async def _random_discovery_loop(self) -> None:
        await self.wait_until_ready()
        await asyncio.sleep(SETTINGS.random_discovery_initial_delay_seconds)

        while not self.is_closed():
            try:
                if self.card_catalog_service is None:
                    raise RuntimeError("Le catalogue de cartes n'est pas initialisé.")
                card = await self.card_catalog_service.discover_random()
                LOGGER.info(
                    "Carte découverte aléatoirement et enregistrée : %s (%s).",
                    card.display_name,
                    card.ygoprodeck_id,
                )
            except asyncio.CancelledError:
                raise
            except Exception:
                LOGGER.exception("La découverte aléatoire d'une carte a échoué.")

            base_seconds = SETTINGS.random_discovery_interval_minutes * 60
            jittered_seconds = max(3600, int(base_seconds * random.uniform(0.85, 1.15)))
            await asyncio.sleep(jittered_seconds)

    async def on_ready(self) -> None:
        if self.user is None:
            return

        LOGGER.info(
            "Madame Rilliona connectée en tant que %s (%s).",
            self.user,
            self.user.id,
        )

        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.watching,
                name="les cartes et les archétypes",
            )
        )

    async def close(self) -> None:
        if self._random_discovery_task is not None:
            self._random_discovery_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._random_discovery_task
            self._random_discovery_task = None

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
