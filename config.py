from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "oui"}


def _env_int(name: str, default: int, *, minimum: int) -> int:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError as error:
        raise RuntimeError(f"{name} doit être un nombre entier.") from error
    return max(minimum, value)


@dataclass(frozen=True, slots=True)
class Settings:
    discord_token: str
    database_url: str
    guild_id: int | None
    card_image_directory: Path
    log_level: str
    random_discovery_enabled: bool
    random_discovery_interval_minutes: int
    random_discovery_initial_delay_seconds: int

    @classmethod
    def from_env(cls) -> "Settings":
        token = os.getenv("DISCORD_TOKEN", "").strip()
        database_url = os.getenv("DATABASE_URL", "").strip()

        if not token:
            raise RuntimeError("La variable DISCORD_TOKEN est absente.")
        if not database_url:
            raise RuntimeError("La variable DATABASE_URL est absente.")

        raw_guild_id = os.getenv("GUILD_ID", "").strip()
        guild_id: int | None = None
        if raw_guild_id:
            try:
                guild_id = int(raw_guild_id)
            except ValueError as error:
                raise RuntimeError("GUILD_ID doit être un identifiant numérique.") from error

        image_directory = Path(
            os.getenv("CARD_IMAGE_DIRECTORY", "/app/data/card_images")
        ).expanduser()

        return cls(
            discord_token=token,
            database_url=database_url,
            guild_id=guild_id,
            card_image_directory=image_directory,
            log_level=os.getenv("LOG_LEVEL", "INFO").upper().strip() or "INFO",
            random_discovery_enabled=_env_bool("RANDOM_DISCOVERY_ENABLED", True),
            random_discovery_interval_minutes=_env_int(
                "RANDOM_DISCOVERY_INTERVAL_MINUTES",
                360,
                minimum=60,
            ),
            random_discovery_initial_delay_seconds=_env_int(
                "RANDOM_DISCOVERY_INITIAL_DELAY_SECONDS",
                300,
                minimum=30,
            ),
        )


SETTINGS = Settings.from_env()
