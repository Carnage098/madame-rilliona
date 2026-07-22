from __future__ import annotations

import asyncio
from typing import Any

import aiohttp


class CardApiService:
    BASE_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php"
    RANDOM_URL = "https://db.ygoprodeck.com/api/v7/randomcard.php"
    ARCHETYPES_URL = "https://db.ygoprodeck.com/api/v7/archetypes.php"

    def __init__(self, timeout_seconds: int = 90) -> None:
        self.timeout = aiohttp.ClientTimeout(total=timeout_seconds)
        self.headers = {"User-Agent": "Madame-Rilliona/2.7"}

    async def _request_json(
        self,
        session: aiohttp.ClientSession,
        url: str,
        params: dict[str, str] | None = None,
        *,
        empty_on_not_found: bool = False,
    ) -> Any:
        async with session.get(url, params=params) as response:
            if response.status == 429:
                raise RuntimeError(
                    "YGOPRODeck limite temporairement les requêtes. Réessaie dans quelques instants."
                )
            if empty_on_not_found and response.status in {400, 404}:
                return None
            response.raise_for_status()
            return await response.json(content_type=None)

    async def _fetch_cards(
        self,
        session: aiohttp.ClientSession,
        params: dict[str, str] | None = None,
        *,
        empty_on_not_found: bool = False,
    ) -> list[dict[str, Any]]:
        payload = await self._request_json(
            session,
            self.BASE_URL,
            params,
            empty_on_not_found=empty_on_not_found,
        )
        if payload is None:
            return []
        if not isinstance(payload, dict):
            if empty_on_not_found:
                return []
            raise RuntimeError("Réponse YGOPRODeck invalide.")
        data = payload.get("data")
        if not isinstance(data, list):
            if empty_on_not_found:
                return []
            raise RuntimeError("Réponse YGOPRODeck invalide : champ data absent.")
        return [item for item in data if isinstance(item, dict)]

    async def fetch_catalogues(self) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Télécharge le catalogue anglais et, si possible, sa traduction française."""
        async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
            english_task = self._fetch_cards(session)
            french_task = self._fetch_cards(session, {"language": "fr"})
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
            return await self._fetch_cards(
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
            cards = await self._fetch_cards(
                session,
                params,
                empty_on_not_found=True,
            )
        return cards[0] if cards else None

    async def fetch_by_archetype(
        self,
        archetype: str,
        *,
        language: str | None = None,
    ) -> list[dict[str, Any]]:
        params = {"archetype": archetype.strip()}
        if language:
            params["language"] = language
        async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
            return await self._fetch_cards(
                session,
                params,
                empty_on_not_found=True,
            )

    async def fetch_archetype_names(self) -> list[str]:
        async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
            payload = await self._request_json(session, self.ARCHETYPES_URL)

        if not isinstance(payload, list):
            raise RuntimeError("La liste des archétypes YGOPRODeck est invalide.")

        names: list[str] = []
        for item in payload:
            if isinstance(item, str) and item.strip():
                names.append(item.strip())
            elif isinstance(item, dict):
                value = item.get("archetype_name") or item.get("name")
                if value:
                    names.append(str(value).strip())
        return sorted(set(names), key=str.casefold)

    async def fetch_random(self) -> dict[str, Any] | None:
        async with aiohttp.ClientSession(timeout=self.timeout, headers=self.headers) as session:
            payload = await self._request_json(session, self.RANDOM_URL)

        if isinstance(payload, dict):
            data = payload.get("data")
            if isinstance(data, list) and data and isinstance(data[0], dict):
                return data[0]
            if payload.get("id") is not None:
                return payload
        return None
