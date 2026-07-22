from __future__ import annotations

from typing import Any

from models.card import Card
from repositories.card_repository import CardRepository
from services.card_api_service import CardApiService


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
