from __future__ import annotations

import asyncio
from typing import Any

import aiohttp


class CardApiService:
    BASE_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php"

    def __init__(self, timeout_seconds: int = 90) -> None:
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    async def _fetch(self, session: aiohttp.ClientSession, language: str | None) -> list[dict[str, Any]]:
        params = {"language": language} if language else None
        async with session.get(self.BASE_URL, params=params) as response:
            if response.status == 429:
                raise RuntimeError("YGOPRODeck limite temporairement les requêtes. Réessaie plus tard.")
            response.raise_for_status()
            payload = await response.json(content_type=None)
            data = payload.get("data")
            if not isinstance(data, list):
                raise RuntimeError("Réponse YGOPRODeck invalide : champ data absent.")
            return data

    async def fetch_catalogues(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        headers = {"User-Agent": "Madame-Rilliona/2.3"}
        async with aiohttp.ClientSession(timeout=self.timeout, headers=headers) as session:
            english_task = self._fetch(session, None)
            french_task = self._fetch(session, "fr")
            english, french = await asyncio.gather(english_task, french_task)
        return english, french
