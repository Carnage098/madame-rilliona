
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
from urllib.parse import urlparse

import aiohttp


class CardImageService:
    """Télécharge chaque image une seule fois et la sert depuis le cache local."""

    def __init__(
        self,
        *,
        session: aiohttp.ClientSession,
        image_directory: Path,
    ) -> None:
        self._session = session
        self._image_directory = image_directory
        self._locks: dict[str, asyncio.Lock] = {}

    async def get_cached_image(
        self,
        card_id: int,
        image_url: str | None,
    ) -> Path | None:
        if not image_url:
            return None

        extension = Path(urlparse(image_url).path).suffix.lower()
        if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
            extension = ".jpg"

        destination = self._image_directory / f"{card_id}{extension}"
        if destination.exists() and destination.stat().st_size > 0:
            return destination

        lock_key = hashlib.sha256(str(destination).encode()).hexdigest()
        lock = self._locks.setdefault(lock_key, asyncio.Lock())

        async with lock:
            if destination.exists() and destination.stat().st_size > 0:
                return destination

            destination.parent.mkdir(parents=True, exist_ok=True)
            temporary = destination.with_suffix(destination.suffix + ".tmp")

            try:
                async with self._session.get(image_url) as response:
                    response.raise_for_status()
                    content = await response.read()

                if not content:
                    return None

                temporary.write_bytes(content)
                temporary.replace(destination)
                return destination

            except (aiohttp.ClientError, asyncio.TimeoutError, OSError):
                if temporary.exists():
                    temporary.unlink(missing_ok=True)
                return None
