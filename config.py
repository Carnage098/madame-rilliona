from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True, slots=True)
class Settings:
    discord_token: str
    database_url: str
    guild_id: int | None
    card_image_directory: Path
    log_level: str

    @classmethod
    def from_environment(cls) -> "Settings":
        token = os.getenv("DISCORD_TOKEN", "").strip()
        database_url = os.getenv("DATABASE_URL", "").strip()
        guild_id_raw = os.getenv("GUILD_ID", "").strip()

        if not token:
            raise RuntimeError(
                "La variable d'environnement DISCORD_TOKEN est absente."
            )

        if not database_url:
            raise RuntimeError(
                "La variable d'environnement DATABASE_URL est absente."
            )

        guild_id = int(guild_id_raw) if guild_id_raw else None

        image_directory = Path(
            os.getenv("CARD_IMAGE_DIRECTORY", "data/card_images")
        )

        return cls(
            discord_token=token,
            database_url=database_url,
            guild_id=guild_id,
            card_image_directory=image_directory,
            log_level=os.getenv("LOG_LEVEL", "INFO"),
        )
