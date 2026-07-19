from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

from models.card import CardRecord
from repositories.card_repository import CardRepository
from services.card_api_service import CardApiService
from utils.text import normalize_card_name


@dataclass(frozen=True, slots=True)
class CardSyncReport:
    before_count: int
    processed: int
    after_count: int
    english_received: int
    french_received: int

    @property
    def new_cards(self) -> int:
        return max(0, self.after_count - self.before_count)


class CardCatalogService:
    def __init__(
        self,
        *,
        repository: CardRepository,
        api: CardApiService,
    ) -> None:
        self._repository = repository
        self._api = api
        self._sync_lock = asyncio.Lock()

    @property
    def sync_in_progress(self) -> bool:
        return self._sync_lock.locked()

    async def find_card(self, query: str) -> CardRecord | None:
        local = await self._repository.find_best_match(query)
        if local is not None:
            return local

        french_results = await self._api.search_cards(
            query,
            language="fr",
            limit=25,
        )
        english_results = await self._api.search_cards(
            query,
            language=None,
            limit=25,
        )

        chosen = self._choose_api_result(
            query,
            french_results or english_results,
        )
        if chosen is None:
            return None

        card_id = int(chosen["id"])
        english, french = await asyncio.gather(
            self._api.fetch_card_by_id(card_id),
            self._api.fetch_card_by_id(card_id, language="fr"),
        )

        if english is None:
            english = chosen

        record = self._merge_card_data(english, french)
        await self._repository.upsert(record)
        return record

    async def sync_all(self) -> CardSyncReport:
        if self._sync_lock.locked():
            raise RuntimeError("Une synchronisation est déjà en cours.")

        async with self._sync_lock:
            before_count = await self._repository.count()

            english_cards, french_cards = await asyncio.gather(
                self._api.fetch_all_cards(language=None, include_misc=True),
                self._api.fetch_all_cards(language="fr", include_misc=True),
            )

            french_by_id = {
                int(card["id"]): card
                for card in french_cards
                if card.get("id") is not None
            }

            merged = (
                self._merge_card_data(
                    english,
                    french_by_id.get(int(english["id"])),
                )
                for english in english_cards
                if english.get("id") is not None
            )

            processed = await self._repository.bulk_upsert(merged)
            after_count = await self._repository.count()

            return CardSyncReport(
                before_count=before_count,
                processed=processed,
                after_count=after_count,
                english_received=len(english_cards),
                french_received=len(french_cards),
            )

    @staticmethod
    def _choose_api_result(
        query: str,
        results: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if not results:
            return None

        normalized_query = normalize_card_name(query)

        exact = next(
            (
                card
                for card in results
                if normalize_card_name(str(card.get("name", "")))
                == normalized_query
            ),
            None,
        )
        return exact or results[0]

    @staticmethod
    def _merge_card_data(
        english: dict[str, Any],
        french: dict[str, Any] | None,
    ) -> CardRecord:
        french = french or {}
        card_images = english.get("card_images") or []
        first_image = (
            card_images[0]
            if card_images and isinstance(card_images[0], dict)
            else {}
        )

        english_misc = CardCatalogService._first_dict(
            english.get("misc_info")
        )
        french_misc = CardCatalogService._first_dict(
            french.get("misc_info")
        )
        banlist = CardCatalogService._first_dict(
            english.get("banlist_info")
        )

        name_en = str(english.get("name") or "Carte inconnue")
        name_fr_raw = french.get("name")
        name_fr = str(name_fr_raw) if name_fr_raw else None

        return CardRecord(
            ygoprodeck_id=int(english["id"]),
            konami_id=CardCatalogService._optional_int(
                english_misc.get("konami_id")
                or french_misc.get("konami_id")
            ),
            name_en=name_en,
            name_fr=name_fr,
            normalized_name_en=normalize_card_name(name_en),
            normalized_name_fr=(
                normalize_card_name(name_fr) if name_fr else None
            ),
            description_en=CardCatalogService._optional_str(
                english.get("desc")
            ),
            description_fr=CardCatalogService._optional_str(
                french.get("desc")
            ),
            card_type_en=CardCatalogService._optional_str(
                english.get("type")
            ),
            card_type_fr=CardCatalogService._optional_str(
                french.get("type")
            ),
            frame_type=CardCatalogService._optional_str(
                english.get("frameType")
            ),
            race_en=CardCatalogService._optional_str(
                english.get("race")
            ),
            race_fr=CardCatalogService._optional_str(
                french.get("race")
            ),
            archetype_en=CardCatalogService._optional_str(
                english.get("archetype")
            ),
            archetype_fr=CardCatalogService._optional_str(
                french.get("archetype")
            ),
            attribute=CardCatalogService._optional_str(
                english.get("attribute")
            ),
            attack=CardCatalogService._optional_int(
                english.get("atk")
            ),
            defense=CardCatalogService._optional_int(
                english.get("def")
            ),
            level=CardCatalogService._optional_int(
                english.get("level")
            ),
            scale=CardCatalogService._optional_int(
                english.get("scale")
            ),
            link_value=CardCatalogService._optional_int(
                english.get("linkval")
            ),
            link_markers=[
                str(marker)
                for marker in (english.get("linkmarkers") or [])
            ],
            image_url=CardCatalogService._optional_str(
                first_image.get("image_url")
            ),
            image_small_url=CardCatalogService._optional_str(
                first_image.get("image_url_small")
            ),
            image_cropped_url=CardCatalogService._optional_str(
                first_image.get("image_url_cropped")
            ),
            ygoprodeck_url=CardCatalogService._optional_str(
                english.get("ygoprodeck_url")
            ),
            formats=[
                str(item)
                for item in (
                    english_misc.get("formats")
                    or french_misc.get("formats")
                    or []
                )
            ],
            ban_tcg=CardCatalogService._optional_str(
                banlist.get("ban_tcg")
            ),
            ban_ocg=CardCatalogService._optional_str(
                banlist.get("ban_ocg")
            ),
            ban_goat=CardCatalogService._optional_str(
                banlist.get("ban_goat")
            ),
            raw_data_en=english,
            raw_data_fr=french,
        )

    @staticmethod
    def _first_dict(value: Any) -> dict[str, Any]:
        if isinstance(value, dict):
            return value
        if (
            isinstance(value, list)
            and value
            and isinstance(value[0], dict)
        ):
            return value[0]
        return {}

    @staticmethod
    def _optional_str(value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None
