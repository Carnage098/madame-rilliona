from __future__ import annotations

import logging

import aiohttp
import discord
from discord.ext import commands

from config import SETTINGS
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
    """Bot Discord principal de Madame Rilliona."""

    def __init__(self) -> None:
        # Les commandes slash ne nécessitent pas l'intent message_content.
        intents = discord.Intents.default()

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None,
        )

        self.database: Database | None = None
        self.http_session: aiohttp.ClientSession | None = None

        self.card_repository: CardRepository | None = None
        self.archetype_repository: ArchetypeRepository | None = None
        self.combo_repository: ComboRepository | None = None

        self.card_api: CardApiService | None = None
        self.card_catalog: CardCatalogService | None = None
        self.card_images: CardImageService | None = None
        self.combo_service: ComboService | None = None

    async def setup_hook(self) -> None:
        """Initialise PostgreSQL, les services, les cogs et les commandes."""

        # La classe Database ne possède pas initialize().
        # Il faut ouvrir le pool, puis appliquer le schéma.
        self.database = Database(SETTINGS.database_url)
        await self.database.connect()
        await self.database.initialize_schema()
        logging.info("Connexion PostgreSQL établie et schéma vérifié.")

        timeout = aiohttp.ClientTimeout(
            total=180,
            connect=30,
        )

        self.http_session = aiohttp.ClientSession(
            timeout=timeout,
            headers={
                "User-Agent": (
                    "Madame-Rilliona-Discord-Bot/2.2 "
                    "(Yu-Gi-Oh card and combo library)"
                )
            },
        )

        # Repositories
        self.card_repository = CardRepository(self.database)
        self.archetype_repository = ArchetypeRepository(self.database)
        self.combo_repository = ComboRepository(self.database)

        # Services
        self.card_api = CardApiService(self.http_session)

        self.card_catalog = CardCatalogService(
            repository=self.card_repository,
            api=self.card_api,
        )

        self.card_images = CardImageService(
            session=self.http_session,
            image_directory=SETTINGS.card_image_directory,
        )

        self.combo_service = ComboService(
            archetypes=self.archetype_repository,
            combos=self.combo_repository,
        )

        # Chargement des modules Discord
        for extension in COGS:
            try:
                await self.load_extension(extension)
                logging.info("Cog chargé : %s", extension)
            except Exception:
                logging.exception(
                    "Impossible de charger le cog : %s",
                    extension,
                )
                raise

        # Synchronisation rapide sur un serveur de développement si GUILD_ID existe.
        if SETTINGS.guild_id:
            guild = discord.Object(id=SETTINGS.guild_id)
            self.tree.copy_global_to(guild=guild)
            synced = await self.tree.sync(guild=guild)

            logging.info(
                "%s commande(s) synchronisée(s) sur le serveur %s.",
                len(synced),
                SETTINGS.guild_id,
            )
        else:
            synced = await self.tree.sync()
            logging.info(
                "%s commande(s) globale(s) synchronisée(s).",
                len(synced),
            )

    async def on_ready(self) -> None:
        if self.user is None:
            return

        logging.info(
            "Madame Rilliona est connectée : %s (%s)",
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
        """Ferme proprement les connexions avant l'arrêt du bot."""

        if self.http_session is not None:
            if not self.http_session.closed:
                await self.http_session.close()
            self.http_session = None

        if self.database is not None:
            await self.database.close()
            self.database = None

        await super().close()


def main() -> None:
    logging.basicConfig(
        level=getattr(
            logging,
            SETTINGS.log_level.upper(),
            logging.INFO,
        ),
        format=(
            "[%(asctime)s] [%(levelname)s] "
            "%(name)s: %(message)s"
        ),
    )

    bot = MadameRillionaBot()
    bot.run(
        SETTINGS.discord_token,
        log_handler=None,
    )


if __name__ == "__main__":
    main()
