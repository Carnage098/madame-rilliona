from __future__ import annotations

import asyncio
from typing import Any

import aiohttp


class CardApiError(RuntimeError):
    pass


class CardNotFoundError(CardApiError):
    pass


class CardApiService:
    BASE_URL = "https://db.ygoprodeck.com/api/v7/cardinfo.php"
    MAX_RETRIES = 4

    def __init__(self, session: aiohttp.ClientSession) -> None:
        self._session = session

    async def fetch_all_cards(
        self,
        *,
        language: str | None = None,
        include_misc: bool = True,
    ) -> list[dict[str, Any]]:
        params: dict[str, str] = {}
        if language:
            params["language"] = language
        if include_misc:
            params["misc"] = "yes"

        payload = await self._request(params)
        return self._extract_cards(payload)

    async def fetch_card_by_id(
        self,
        card_id: int,
        *,
        language: str | None = None,
    ) -> dict[str, Any] | None:
        params = {
            "id": str(card_id),
            "misc": "yes",
        }
        if language:
            params["language"] = language

        try:
            payload = await self._request(params)
        except CardNotFoundError:
            return None

        cards = self._extract_cards(payload)
        return cards[0] if cards else None

    async def search_cards(
        self,
        query: str,
        *,
        language: str | None = None,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        params = {
            "fname": query,
            "misc": "yes",
        }
        if language:
            params["language"] = language

        try:
            payload = await self._request(params)
        except CardNotFoundError:
            return []

        return self._extract_cards(payload)[:limit]

    async def _request(self, params: dict[str, str]) -> dict[str, Any]:
        last_error: Exception | None = None

        for attempt in range(self.MAX_RETRIES):
            try:
                async with self._session.get(
                    self.BASE_URL,
                    params=params,
                ) as response:
                    if response.status == 400:
                        raise CardNotFoundError(
                            "Aucune carte ne correspond à la recherche."
                        )

                    if response.status == 429:
                        retry_after = float(
                            response.headers.get("Retry-After", "2")
                        )
                        await asyncio.sleep(max(1.0, retry_after))
                        continue

                    if response.status >= 500:
                        body = await response.text()
                        raise CardApiError(
                            f"YGOPRODeck indisponible ({response.status}) : "
                            f"{body[:200]}"
                        )

                    response.raise_for_status()
                    payload = await response.json(content_type=None)

                    if not isinstance(payload, dict):
                        raise CardApiError(
                            "Réponse YGOPRODeck inattendue."
                        )

                    return payload

            except CardNotFoundError:
                raise
            except (aiohttp.ClientError, asyncio.TimeoutError, CardApiError) as exc:
                last_error = exc
                if attempt + 1 >= self.MAX_RETRIES:
                    break
                await asyncio.sleep(2 ** attempt)

        raise CardApiError(
            "Impossible de joindre YGOPRODeck après plusieurs tentatives."
        ) from last_error

    @staticmethod
    def _extract_cards(payload: dict[str, Any]) -> list[dict[str, Any]]:
        data = payload.get("data", [])
        if not isinstance(data, list):
            raise CardApiError("Le champ 'data' de l'API est invalide.")
        return [item for item in data if isinstance(item, dict)]
