from __future__ import annotations

import asyncio
from collections import Counter
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any

from models.card import Card
from repositories.card_repository import CardRepository
from services.card_api_service import CardApiService
from utils.text import normalize_search_text


@dataclass(frozen=True, slots=True)
class ArchetypeSyncResult:
    requested_name: str
    canonical_name: str
    imported_count: int


class CardCatalogService:
    def __init__(self, api: CardApiService, repository: CardRepository) -> None:
        self.api = api
        self.repository = repository
        self._archetype_names_cache: tuple[str, ...] = ()
        self._archetype_sync_lock = asyncio.Lock()

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

    @staticmethod
    def _string_tuple(value: Any) -> tuple[str, ...]:
        if not isinstance(value, list):
            return ()
        return tuple(str(item) for item in value if item)

    @staticmethod
    def _category(card_type: str, frame_type: str) -> str:
        lowered_type = card_type.casefold()
        lowered_frame = frame_type.casefold()
        if "spell card" in lowered_type or lowered_frame == "spell":
            return "Magie"
        if "trap card" in lowered_type or lowered_frame == "trap":
            return "Piège"
        if "skill" in lowered_type or lowered_frame == "skill":
            return "Compétence"
        if "token" in lowered_type or lowered_frame == "token":
            return "Jeton"
        if "monster" in lowered_type or lowered_frame in {
            "normal",
            "effect",
            "ritual",
            "fusion",
            "synchro",
            "xyz",
            "link",
            "normal_pendulum",
            "effect_pendulum",
            "ritual_pendulum",
            "fusion_pendulum",
            "synchro_pendulum",
            "xyz_pendulum",
        }:
            return "Monstre"
        return "Autre"

    @staticmethod
    def _deck_section(category: str, card_type: str, frame_type: str) -> str:
        lowered = f"{card_type} {frame_type}".casefold()
        if any(keyword in lowered for keyword in ("fusion", "synchro", "xyz", "link")):
            return "Extra Deck"
        if category == "Monstre":
            return "Main Deck"
        if category in {"Magie", "Piège"}:
            return "Zone Magie/Piège"
        return "Hors Deck principal"

    @classmethod
    def _classification(
        cls,
        *,
        category: str,
        deck_section: str,
        card_type: str,
        race: str | None,
        attribute: str | None,
        typeline: tuple[str, ...],
    ) -> str:
        details: list[str] = [category, deck_section]
        if typeline:
            details.extend(typeline)
        elif card_type:
            details.append(card_type)
        if race and race not in details:
            details.append(race)
        if attribute:
            details.append(attribute)
        return " • ".join(dict.fromkeys(details))

    def _build_card(
        self,
        english: dict[str, Any],
        french: dict[str, Any] | None,
        *,
        import_source: str,
    ) -> Card:
        card_type = str(english.get("type") or "")
        frame_type = str(english.get("frameType") or "")
        category = self._category(card_type, frame_type)
        deck_section = self._deck_section(category, card_type, frame_type)
        race = str(english.get("race") or "") or None
        attribute = str(english.get("attribute") or "") or None
        typeline = self._string_tuple(english.get("typeline"))
        banlist = english.get("banlist_info")
        if not isinstance(banlist, dict):
            banlist = {}

        raw_level = self._integer(english.get("level"))
        is_xyz = "xyz" in f"{card_type} {frame_type}".casefold()

        return Card(
            ygoprodeck_id=int(english["id"]),
            name_en=str(english.get("name") or "Carte inconnue"),
            name_fr=str(french.get("name")) if french and french.get("name") else None,
            description_en=str(english.get("desc") or ""),
            description_fr=str(french.get("desc")) if french and french.get("desc") else None,
            card_type=card_type or None,
            frame_type=frame_type or None,
            card_category=category,
            deck_section=deck_section,
            classification=self._classification(
                category=category,
                deck_section=deck_section,
                card_type=card_type,
                race=race,
                attribute=attribute,
                typeline=typeline,
            ),
            race=race,
            archetype=str(english.get("archetype") or "") or None,
            attribute=attribute,
            level=None if is_xyz else raw_level,
            rank=raw_level if is_xyz else self._integer(english.get("rank")),
            linkval=self._integer(english.get("linkval")),
            atk=self._integer(english.get("atk")),
            defense=self._integer(english.get("def")),
            scale=self._integer(english.get("scale")),
            typeline=typeline,
            link_markers=self._string_tuple(english.get("linkmarkers")),
            ban_tcg=str(banlist.get("ban_tcg")) if banlist.get("ban_tcg") else None,
            ban_ocg=str(banlist.get("ban_ocg")) if banlist.get("ban_ocg") else None,
            ban_goat=str(banlist.get("ban_goat")) if banlist.get("ban_goat") else None,
            ygoprodeck_url=str(english.get("ygoprodeck_url") or "") or None,
            image_url=self._image(english, "image_url"),
            image_small_url=self._image(english, "image_url_small"),
            import_source=import_source,
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
            self._build_card(
                card,
                french_by_id.get(int(card["id"])),
                import_source="full_catalogue",
            )
            for card in english_cards
            if isinstance(card, dict) and card.get("id") is not None
        ]
        return await self.repository.upsert_many(cards)

    async def find_or_fetch(self, query: str) -> Card | None:
        """Cherche localement puis interroge l'API et enregistre le résultat complet."""
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

        english: dict[str, Any] | None = None
        if french is not None and french.get("id") is not None:
            english = await self.api.fetch_by_id(int(french["id"]))
        else:
            english_matches = await self.api.search(normalized)
            english = self._best_match(normalized, english_matches)

        if english is None:
            return None

        card_id = int(english["id"])
        if french is None or int(french.get("id", -1)) != card_id:
            french = await self.api.fetch_by_id(card_id, language="fr")

        card = self._build_card(english, french, import_source="search")
        await self.repository.upsert(card)
        return card

    async def _archetype_names(self, *, refresh: bool = False) -> tuple[str, ...]:
        if refresh or not self._archetype_names_cache:
            names = await self.api.fetch_archetype_names()
            self._archetype_names_cache = tuple(names)
        return self._archetype_names_cache

    @staticmethod
    def _archetype_score(query: str, candidate: str) -> float:
        normalized_candidate = normalize_search_text(candidate)
        if not query or not normalized_candidate:
            return 0.0
        if query == normalized_candidate:
            return 1000.0
        if normalized_candidate.startswith(query) or query.startswith(normalized_candidate):
            return 900.0
        if query in normalized_candidate or normalized_candidate in query:
            return 800.0
        return SequenceMatcher(None, query, normalized_candidate).ratio() * 600.0

    async def resolve_archetype_name(self, query: str) -> str | None:
        requested = query.strip()
        normalized_query = normalize_search_text(requested)
        if not normalized_query:
            return None

        names = await self._archetype_names()
        ranked = sorted(
            names,
            key=lambda candidate: self._archetype_score(normalized_query, candidate),
            reverse=True,
        )
        if ranked and self._archetype_score(normalized_query, ranked[0]) >= 430.0:
            return ranked[0]

        # Un nom français peut ne pas ressembler au nom d'archétype anglais.
        # On cherche alors des cartes françaises et on récupère leur champ archetype.
        french_matches = await self.api.search(requested, language="fr")
        inferred = Counter(
            str(card.get("archetype"))
            for card in french_matches
            if card.get("archetype")
        )
        for candidate, _count in inferred.most_common():
            if candidate in names:
                return candidate

        # Dernier essai : l'API peut accepter directement un nom canonique récent
        # absent du cache local.
        direct_cards = await self.api.fetch_by_archetype(requested)
        if direct_cards:
            canonical = str(direct_cards[0].get("archetype") or requested).strip()
            if canonical:
                return canonical
        return None

    async def synchronize_archetype(self, query: str) -> ArchetypeSyncResult:
        async with self._archetype_sync_lock:
            canonical = await self.resolve_archetype_name(query)
            if canonical is None:
                raise ValueError(
                    "Cet archétype n'a pas été reconnu par YGOPRODeck. Essaie son nom anglais ou le nom français d'une de ses cartes."
                )

            english_cards, french_cards = await asyncio.gather(
                self.api.fetch_by_archetype(canonical),
                self.api.fetch_by_archetype(canonical, language="fr"),
            )
            if not english_cards:
                raise ValueError("Aucune carte n'a été trouvée pour cet archétype.")

            french_by_id = {
                int(card["id"]): card
                for card in french_cards
                if card.get("id") is not None
            }
            cards = [
                self._build_card(
                    english,
                    french_by_id.get(int(english["id"])),
                    import_source=f"archetype:{canonical}",
                )
                for english in english_cards
                if english.get("id") is not None
            ]
            imported = await self.repository.upsert_many(cards)
            return ArchetypeSyncResult(
                requested_name=query.strip(),
                canonical_name=canonical,
                imported_count=imported,
            )

    async def discover_random(self) -> Card:
        english = await self.api.fetch_random()
        if english is None or english.get("id") is None:
            raise RuntimeError("YGOPRODeck n'a pas renvoyé de carte aléatoire valide.")
        card_id = int(english["id"])
        french = await self.api.fetch_by_id(card_id, language="fr")
        card = self._build_card(english, french, import_source="random_discovery")
        await self.repository.upsert(card)
        return card
