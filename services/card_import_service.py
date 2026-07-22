from __future__ import annotations

import contextlib
import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from models.card import Card
from repositories.card_repository import CardRepository
from services.card_catalog_service import CardCatalogService
from services.card_image_service import CardImageService, PNG_SIGNATURE


@dataclass(frozen=True, slots=True)
class CardVerificationResult:
    card: Card | None
    checks: dict[str, bool]
    local_image_path: Path | None = None

    @property
    def verified(self) -> bool:
        return self.card is not None and all(self.checks.values())

    @property
    def summary(self) -> str:
        labels = {
            "database": "Présente dans PostgreSQL",
            "name": "Nom enregistré",
            "effect": "Effet/description enregistré",
            "classification": "Classement enregistré",
            "image": "Image disponible",
        }
        return "\n".join(
            f"{'✅' if value else '❌'} {labels.get(key, key)}"
            for key, value in self.checks.items()
        )


@dataclass(frozen=True, slots=True)
class CardImportResult:
    card: Card
    verification: CardVerificationResult
    import_log_id: int
    source_type: str
    source_reference: str | None


class CardImportService:
    """Import staff depuis une URL de référence ou une image PNG."""

    YGOPRODECK_HOSTS = {
        "ygoprodeck.com",
        "www.ygoprodeck.com",
        "app.ygoprodeck.com",
        "api.ygoprodeck.com",
        "db.ygoprodeck.com",
        "images.ygoprodeck.com",
    }
    IMAGE_ID_PATTERN = re.compile(
        r"/images/cards(?:_small|_cropped)?/(?P<card_id>\d+)\.(?:jpg|jpeg|png|webp)$",
        re.IGNORECASE,
    )
    CARD_PAGE_PATTERN = re.compile(r"^/card/(?P<slug>[^/?#]+)$", re.IGNORECASE)
    GENERIC_FILENAME_STEMS = {
        "image",
        "img",
        "photo",
        "picture",
        "screenshot",
        "capture",
        "capture d ecran",
        "capture d'écran",
        "carte",
        "card",
        "unknown",
        "sans titre",
    }

    def __init__(
        self,
        *,
        catalog: CardCatalogService,
        repository: CardRepository,
        images: CardImageService,
        max_image_bytes: int,
    ) -> None:
        self.catalog = catalog
        self.repository = repository
        self.images = images
        self.max_image_bytes = max_image_bytes

    @staticmethod
    def _clean_reference(value: str | None, *, limit: int = 2048) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned[:limit] or None

    @classmethod
    def identifier_from_url(cls, url: str, *, name_hint: str | None = None) -> str:
        cleaned_url = url.strip()
        if len(cleaned_url) > 2048:
            raise ValueError("L'URL est trop longue.")

        parsed = urlsplit(cleaned_url)
        if parsed.scheme.lower() != "https" or not parsed.hostname:
            raise ValueError("Utilise une URL publique commençant par https://.")

        host = parsed.hostname.lower().rstrip(".")
        hint = (name_hint or "").strip()

        # Pour un site tiers, le bot ne télécharge pas la page : le nom sert de clé
        # vers YGOPRODeck. Cela évite les accès à des adresses privées et les scrapers fragiles.
        if host not in cls.YGOPRODECK_HOSTS:
            if hint:
                return hint
            raise ValueError(
                "Pour un site autre que YGOPRODeck, indique aussi le nom exact de la carte."
            )

        query = parse_qs(parsed.query)
        for key in ("id", "card_id"):
            value = query.get(key, [""])[0].strip()
            if value.isdigit():
                return value
        for key in ("name", "fname", "search"):
            value = query.get(key, [""])[0].strip()
            if value:
                return value

        image_match = cls.IMAGE_ID_PATTERN.search(parsed.path)
        if image_match:
            return image_match.group("card_id")

        card_page = cls.CARD_PAGE_PATTERN.match(parsed.path)
        if card_page:
            slug = unquote(card_page.group("slug"))
            # Le nombre final d'une page YGOPRODeck est l'identifiant interne de la page,
            # pas toujours le passcode de la carte. On utilise donc le slug comme nom.
            slug = re.sub(r"-\d+$", "", slug)
            candidate = " ".join(slug.replace("_", "-").split("-"))
            if candidate.strip():
                return candidate.strip()

        if hint:
            return hint
        raise ValueError(
            "Cette URL YGOPRODeck ne contient pas de carte identifiable. "
            "Ajoute aussi son nom dans l'option nom."
        )

    @classmethod
    def identifier_from_filename(
        cls,
        filename: str,
        *,
        name_hint: str | None = None,
    ) -> str:
        hint = (name_hint or "").strip()
        if hint:
            return hint

        stem = unquote(Path(filename).stem)
        stem = stem.replace("_", " ").strip()
        normalized = re.sub(r"[^a-zA-ZÀ-ÿ0-9'’ -]+", " ", stem)
        normalized = " ".join(normalized.split())
        if normalized.isdigit():
            return normalized
        if normalized.casefold() in cls.GENERIC_FILENAME_STEMS or len(normalized) < 3:
            raise ValueError(
                "Le nom du fichier ne permet pas d'identifier la carte. "
                "Renseigne l'option nom avec son nom français ou anglais."
            )
        return normalized

    async def verify_card(
        self,
        card_id: int,
        *,
        require_local_png: bool = False,
    ) -> CardVerificationResult:
        stored = await self.repository.get_by_id(card_id)
        local_image = self.images.staff_png_path(card_id)
        has_local_image = local_image.is_file() and local_image.stat().st_size > 0
        has_any_image = has_local_image or bool(stored and stored.image_url)

        checks = {
            "database": stored is not None,
            "name": bool(stored and stored.name_en.strip()),
            "effect": bool(
                stored
                and (
                    (stored.description_fr and stored.description_fr.strip())
                    or (stored.description_en and stored.description_en.strip())
                )
            ),
            "classification": bool(
                stored and stored.card_type and stored.classification
            ),
            "image": has_local_image if require_local_png else has_any_image,
        }
        return CardVerificationResult(
            card=stored,
            checks=checks,
            local_image_path=local_image if has_local_image else None,
        )

    async def verify_local_query(self, query: str) -> CardVerificationResult | None:
        cleaned = query.strip()
        if not cleaned:
            return None
        if cleaned.isdigit():
            card = await self.repository.get_by_id(int(cleaned))
        else:
            matches = await self.repository.search(cleaned, limit=1)
            if not matches:
                matches = await self.repository.search_normalized(cleaned, limit=1)
            card = matches[0] if matches else None
        if card is None:
            return None
        return await self.verify_card(card.ygoprodeck_id)

    async def _record_failure(
        self,
        *,
        submitted_by: int,
        source_type: str,
        source_reference: str | None,
        original_filename: str | None,
        error: Exception,
    ) -> None:
        # Une panne de journalisation ne doit pas masquer l'erreur d'import initiale.
        with contextlib.suppress(Exception):
            await self.repository.record_import(
                card_id=None,
                submitted_by=submitted_by,
                source_type=source_type,
                source_reference=self._clean_reference(source_reference),
                original_filename=self._clean_reference(original_filename, limit=255),
                status="failed",
                verification_status="failed",
                details=str(error)[:2000],
            )

    async def import_from_url(
        self,
        *,
        url: str,
        name_hint: str | None,
        submitted_by: int,
    ) -> CardImportResult:
        try:
            identifier = self.identifier_from_url(url, name_hint=name_hint)
            found = await self.catalog.find_or_fetch(identifier)
            if found is None:
                raise ValueError(
                    "La carte n'a pas été reconnue dans YGOPRODeck à partir de cette URL."
                )

            card = replace(found, import_source=f"staff_url:{submitted_by}")
            await self.repository.upsert(card)
            verification = await self.verify_card(card.ygoprodeck_id)
            log_id = await self.repository.record_import(
                card_id=card.ygoprodeck_id,
                submitted_by=submitted_by,
                source_type="url",
                source_reference=self._clean_reference(url),
                original_filename=None,
                status="imported" if verification.verified else "incomplete",
                verification_status="verified" if verification.verified else "failed",
                details=json.dumps(verification.checks, ensure_ascii=False),
            )
            stored = verification.card or card
            return CardImportResult(
                card=stored,
                verification=verification,
                import_log_id=log_id,
                source_type="url",
                source_reference=self._clean_reference(url),
            )
        except Exception as error:
            await self._record_failure(
                submitted_by=submitted_by,
                source_type="url",
                source_reference=url,
                original_filename=None,
                error=error,
            )
            raise

    async def import_from_png(
        self,
        *,
        content: bytes,
        filename: str,
        content_type: str | None,
        declared_size: int,
        name_hint: str | None,
        submitted_by: int,
    ) -> CardImportResult:
        source_reference = f"discord-attachment:{filename}"
        try:
            if declared_size > self.max_image_bytes or len(content) > self.max_image_bytes:
                max_mb = self.max_image_bytes / (1024 * 1024)
                raise ValueError(f"L'image dépasse la limite de {max_mb:.1f} Mo.")
            if not filename.casefold().endswith(".png"):
                raise ValueError("Le fichier doit avoir l'extension .png.")
            if content_type and content_type.casefold() not in {
                "image/png",
                "image/x-png",
                "application/octet-stream",
            }:
                raise ValueError("Le fichier transmis n'est pas déclaré comme une image PNG.")
            if not content.startswith(PNG_SIGNATURE):
                raise ValueError("Le contenu du fichier n'est pas un véritable PNG.")

            identifier = self.identifier_from_filename(filename, name_hint=name_hint)
            found = await self.catalog.find_or_fetch(identifier)
            if found is None:
                raise ValueError(
                    "La carte n'a pas été reconnue. Indique son nom officiel dans l'option nom."
                )

            image_path = await self.images.save_staff_png(
                found.ygoprodeck_id,
                content,
            )
            card = replace(found, import_source=f"staff_png:{submitted_by}")
            await self.repository.upsert(card)
            verification = await self.verify_card(
                card.ygoprodeck_id,
                require_local_png=True,
            )
            log_id = await self.repository.record_import(
                card_id=card.ygoprodeck_id,
                submitted_by=submitted_by,
                source_type="png",
                source_reference=source_reference,
                original_filename=self._clean_reference(filename, limit=255),
                status="imported" if verification.verified else "incomplete",
                verification_status="verified" if verification.verified else "failed",
                details=json.dumps(
                    {
                        **verification.checks,
                        "stored_path": str(image_path),
                    },
                    ensure_ascii=False,
                ),
            )
            stored = verification.card or card
            return CardImportResult(
                card=stored,
                verification=verification,
                import_log_id=log_id,
                source_type="png",
                source_reference=source_reference,
            )
        except Exception as error:
            await self._record_failure(
                submitted_by=submitted_by,
                source_type="png",
                source_reference=source_reference,
                original_filename=filename,
                error=error,
            )
            raise
