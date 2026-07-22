from __future__ import annotations

from difflib import SequenceMatcher
from typing import Any

from models.card import Card
from repositories.card_repository import CardRepository
from services.card_api_service import CardApiService
from utils.text import normalize_search_text


class CardCatalogService:
    def __init__(self, api: CardApiService, repository: CardRepository) -> None:
        self.api = api
        self.repository = repository

    @staticmethod
    def _integer(value: Any) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _image(card: dict[str, Any], key: str) -> str | None:
        images = card.get("card_images") or []
        if not images or not isinstance(images[0], dict):
            return None
        value = images[0].get(key)
        return str(value) if value else None

    def _build_card(
        self,
        english: dict[str, Any],
        french: dict[str, Any] | None,
    ) -> Card:
        return Card(
            ygoprodeck_id=int(english["id"]),
            name_en=str(english.get("name") or "Carte inconnue"),
            name_fr=str(french.get("name")) if french and french.get("name") else None,
            description_en=str(english.get("desc") or ""),
            description_fr=str(french.get("desc")) if french and french.get("desc") else None,
            card_type=str(english.get("type") or ""),
            race=str(english.get("race") or ""),
            archetype=str(english.get("archetype") or "") or None,
            attribute=str(english.get("attribute") or "") or None,
            level=self._integer(english.get("level")),
            rank=self._integer(english.get("rank")),
            linkval=self._integer(english.get("linkval")),
            atk=self._integer(english.get("atk")),
            defense=self._integer(english.get("def")),
            scale=self._integer(english.get("scale")),
            image_url=self._image(english, "image_url"),
            image_small_url=self._image(english, "image_url_small"),
        )

    @staticmethod
    def _score(query: str, card: dict[str, Any]) -> float:
        name = normalize_search_text(str(card.get("name") or ""))
        if not query or not name:
            return 0.0
        if name == query:
            return 1000.0
        if name.startswith(query):
            return 900.0
        if query in name:
            return 800.0
        query_tokens = set(query.split())
        if query_tokens and query_tokens.issubset(set(name.split())):
            return 700.0
        return SequenceMatcher(None, query, name).ratio() * 500.0

    def _best_match(
        self,
        query: str,
        cards: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        normalized_query = normalize_search_text(query)
        if not normalized_query or not cards:
            return None
        ranked = sorted(
            cards,
            key=lambda card: self._score(normalized_query, card),
            reverse=True,
        )
        best = ranked[0]
        return best if self._score(normalized_query, best) >= 300.0 else None

    async def synchronize(self) -> int:
        english_cards, french_cards = await self.api.fetch_catalogues()
        french_by_id = {
            int(card["id"]): card
            for card in french_cards
            if isinstance(card, dict) and card.get("id") is not None
        }
        cards = [
            self._build_card(card, french_by_id.get(int(card["id"])))
            for card in english_cards
            if isinstance(card, dict) and card.get("id") is not None
        ]
        return await self.repository.upsert_many(cards)

    async def find_or_fetch(self, query: str) -> Card | None:
        """Cherche localement puis interroge l'API et met le résultat en cache."""
        normalized = query.strip()
        if not normalized:
            return None

        if normalized.isdigit():
            local_by_id = await self.repository.get_by_id(int(normalized))
            if local_by_id is not None:
                return local_by_id

        local = await self.repository.search(normalized, limit=1)
        if local:
            return local[0]

        fuzzy = await self.repository.search_normalized(normalized, limit=1)
        if fuzzy:
            return fuzzy[0]

        french_matches = await self.api.search(normalized, language="fr")
        french = self._best_match(normalized, french_matches)

        english_matches: list[dict[str, Any]] = []
        english: dict[str, Any] | None = None

        if french is not None and french.get("id") is not None:
            card_id = int(french["id"])
            english = await self.api.fetch_by_id(card_id)
        else:
            english_matches = await self.api.search(normalized)
            english = self._best_match(normalized, english_matches)

        if english is None:
            return None

        card_id = int(english["id"])
        if french is None or int(french.get("id", -1)) != card_id:
            french = await self.api.fetch_by_id(card_id, language="fr")

        card = self._build_card(english, french)
        await self.repository.upsert(card)
        return card
