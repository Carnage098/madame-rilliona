from __future__ import annotations

import asyncio
from pathlib import Path

import aiohttp

from models.card import Card


class CardImageService:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    async def get(self, card: Card) -> Path | None:
        if not card.image_url:
            return None
        path = self.directory / f"{card.ygoprodeck_id}.jpg"
        if path.is_file() and path.stat().st_size > 0:
            return path

        async with self._lock:
            if path.is_file() and path.stat().st_size > 0:
                return path
            timeout = aiohttp.ClientTimeout(total=45)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(card.image_url) as response:
                    response.raise_for_status()
                    content = await response.read()
            path.write_bytes(content)
        return path
