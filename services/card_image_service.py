from __future__ import annotations

import asyncio
from pathlib import Path

import aiohttp

from models.card import Card


PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"


class CardImageService:
    def __init__(self, directory: Path) -> None:
        self.directory = directory
        self.directory.mkdir(parents=True, exist_ok=True)
        self._lock = asyncio.Lock()

    def staff_png_path(self, card_id: int) -> Path:
        return self.directory / f"{card_id}.png"

    def _existing_path(self, card_id: int) -> Path | None:
        # Une image PNG envoyée par le staff prend priorité sur l'image distante.
        for suffix in (".png", ".webp", ".jpg", ".jpeg"):
            path = self.directory / f"{card_id}{suffix}"
            if path.is_file() and path.stat().st_size > 0:
                return path
        return None

    async def save_staff_png(self, card_id: int, content: bytes) -> Path:
        if not content.startswith(PNG_SIGNATURE):
            raise ValueError("Le fichier transmis n'est pas un véritable PNG.")
        if len(content) < 24 or content[12:16] != b"IHDR":
            raise ValueError("Le fichier PNG est incomplet ou invalide.")

        width = int.from_bytes(content[16:20], "big")
        height = int.from_bytes(content[20:24], "big")
        if width <= 0 or height <= 0 or width > 12000 or height > 12000:
            raise ValueError("Les dimensions de l'image PNG sont invalides.")

        path = self.staff_png_path(card_id)
        temporary = path.with_suffix(".png.tmp")
        async with self._lock:
            temporary.write_bytes(content)
            temporary.replace(path)
        return path

    async def get(self, card: Card) -> Path | None:
        existing = self._existing_path(card.ygoprodeck_id)
        if existing is not None:
            return existing
        if not card.image_url:
            return None

        path = self.directory / f"{card.ygoprodeck_id}.jpg"
        async with self._lock:
            existing = self._existing_path(card.ygoprodeck_id)
            if existing is not None:
                return existing

            timeout = aiohttp.ClientTimeout(total=45)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(card.image_url) as response:
                    response.raise_for_status()
                    content = await response.read()
            path.write_bytes(content)
        return path
