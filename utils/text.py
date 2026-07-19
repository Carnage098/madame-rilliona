from __future__ import annotations

import re
import unicodedata


_SPACE_RE = re.compile(r"\s+")
_UNWANTED_RE = re.compile(r"[^a-z0-9]+")


def normalize_card_name(value: str) -> str:
    """Normalise un nom pour les recherches françaises et anglaises."""
    decomposed = unicodedata.normalize("NFKD", value.casefold())
    without_accents = "".join(
        character
        for character in decomposed
        if not unicodedata.combining(character)
    )
    cleaned = _UNWANTED_RE.sub(" ", without_accents)
    return _SPACE_RE.sub(" ", cleaned).strip()


def truncate(value: str, maximum: int) -> str:
    if len(value) <= maximum:
        return value
    return value[: maximum - 1].rstrip() + "…"
