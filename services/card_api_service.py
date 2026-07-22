from __future__ import annotations

import asyncio
from typing import Any

import aiohttp


class CardApiService:
    BASE_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php"

    def __init__(self, timeout_seconds: int = 90) -> None:
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.headers = {"User-Agent": "Madame-Rilliona/2.6"}

    async def _fetch(
        self,
        session: aiohttp.ClientSession,
        params: dict[str, str] | None = None,
        *,
        empty_on_not_found: bool = False,
    ) -> list[dict[str, Any]]:
        async with session.get(self.BASE_URL, params=params) as response:
            if response.status == 429:
                raise RuntimeError(
                    "YGOPRODeck limite temporairement les requêtes. Réessaie dans quelques instants."
                )
            if empty_on_not_found and response.status in {400, 404}:
                return []
            response.raise_for_status()
            payload = await response.json(content_type=None)
            data = payload.get("data")
            if not isinstance(data, list):
                if empty_on_not_found:
                    return []
                raise RuntimeError("Réponse YGOPRODeck invalide : champ data absent.")
            return [item for item in data if isinstance(item, dict)]

    async def fetch_catalogues(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Télécharge le catalogue anglais et, si possible, sa traduction française."""
        async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
            english_task = self._fetch(session)
            french_task = self._fetch(session, {"language": "fr"})
            english_result, french_result = await asyncio.gather(
                english_task,
                french_task,
                return_exceptions=True,
            )

        if isinstance(english_result, Exception):
            raise english_result

        french_cards: list[dict[str, Any]] = []
        if not isinstance(french_result, Exception):
            french_cards = french_result

        return english_result, french_cards

    async def search(
        self,
        query: str,
        *,
        language: str | None = None,
    ) -> list[dict[str, Any]]:
        normalized = query.strip()
        if not normalized:
            return []

        params = {"fname": normalized}
        if language:
            params["language"] = language

        async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
            return await self._fetch(
                session,
                params,
                empty_on_not_found=True,
            )

    async def fetch_by_id(
        self,
        card_id: int,
        *,
        language: str | None = None,
    ) -> dict[str, Any] | None:
        params = {"id": str(card_id)}
        if language:
            params["language"] = language

        async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
            cards = await self._fetch(
                session,
                params,
                empty_on_not_found=True,
            )
        return cards[0] if cards else None
