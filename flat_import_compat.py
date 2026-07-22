from __future__ import annotations

"""Compatibilité entre les anciens imports en sous-dossiers et la V2.2 à plat.

La V2.2 de Madame Rilliona garde tous les fichiers Python à la racine du dépôt.
Ce module permet toutefois aux anciens imports tels que
``repositories.archetype_repository`` de résoudre automatiquement les modules
racine comme ``repository_archetypes.py``.
"""

import importlib
import importlib.abc
import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Iterable


ROOT = Path(__file__).resolve().parent
LEGACY_PACKAGES = frozenset({
    "repositories",
    "services",
    "models",
    "cogs",
    "utils",
    "views",
})

# Les noms utilisés dans la version V2.2 « tout à la racine ».
EXPLICIT_ALIASES: dict[str, tuple[str, ...]] = {
    "repositories.archetype_repository": (
        "repository_archetypes",
        "repository_archetype",
        "archetype_repository",
    ),
    "repositories.card_repository": (
        "repository_cards",
        "repository_card",
        "card_repository",
    ),
    "repositories.combo_repository": (
        "repository_combos",
        "repository_combo",
        "combo_repository",
    ),
    "services.combo_service": (
        "service_combos",
        "service_combo",
        "combo_service",
    ),
    "services.card_api_service": (
        "service_card_api",
        "card_api_service",
    ),
    "services.card_catalog_service": (
        "service_card_catalog",
        "card_catalog_service",
    ),
    "services.card_image_service": (
        "service_card_image",
        "card_image_service",
    ),
    "cogs.cards": ("cog_cards", "cards"),
    "cogs.card_admin": ("cog_card_admin", "card_admin"),
    "cogs.archetypes": ("cog_archetypes", "archetypes"),
    "cogs.combos": ("cog_combos", "combos"),
}


def _existing_module(candidates: Iterable[str]) -> str | None:
    """Retourne le premier module Python présent à la racine."""

    for candidate in candidates:
        if not candidate or "." in candidate:
            continue
        if (ROOT / f"{candidate}.py").is_file() or (ROOT / candidate / "__init__.py").is_file():
            return candidate
    return None


def _plural_forms(value: str) -> tuple[str, ...]:
    if value.endswith("s"):
        return value, value[:-1]
    return value, f"{value}s"


def _candidate_names(fullname: str) -> tuple[str, ...]:
    package, module_name = fullname.split(".", 1)
    candidates: list[str] = list(EXPLICIT_ALIASES.get(fullname, ()))
    candidates.append(module_name)

    stem = module_name
    for suffix in ("_repository", "_service", "_model", "_view", "_cog"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
            break

    singular_plural = _plural_forms(stem)

    prefixes = {
        "repositories": ("repository", "repo"),
        "services": ("service",),
        "models": ("model",),
        "cogs": ("cog",),
        "utils": ("util", "utils"),
        "views": ("view",),
    }.get(package, ())

    for prefix in prefixes:
        for form in singular_plural:
            candidates.append(f"{prefix}_{form}")

    for form in singular_plural:
        candidates.extend((form, f"{form}_{package.rstrip('s')}"))

    # Supprime les doublons en conservant l'ordre.
    return tuple(dict.fromkeys(candidates))


class _LegacyPackageLoader(importlib.abc.Loader):
    def create_module(self, spec):  # type: ignore[no-untyped-def]
        return None

    def exec_module(self, module: ModuleType) -> None:
        module.__path__ = []  # type: ignore[attr-defined]
        module.__package__ = module.__name__


class _RootAliasLoader(importlib.abc.Loader):
    def __init__(self, target_name: str) -> None:
        self.target_name = target_name

    def create_module(self, spec):  # type: ignore[no-untyped-def]
        return None

    def exec_module(self, module: ModuleType) -> None:
        target = importlib.import_module(self.target_name)
        preserved = {
            "__name__": module.__name__,
            "__package__": module.__package__,
            "__loader__": module.__loader__,
            "__spec__": module.__spec__,
        }
        for key, value in target.__dict__.items():
            if key in preserved:
                continue
            module.__dict__[key] = value
        module.__dict__.update(preserved)
        module.__dict__["__flat_root_target__"] = self.target_name


class FlatRootCompatibilityFinder(importlib.abc.MetaPathFinder):
    """Résout les anciens chemins de modules vers les fichiers racine."""

    def find_spec(self, fullname: str, path=None, target=None):  # type: ignore[no-untyped-def]
        if fullname in LEGACY_PACKAGES:
            return importlib.util.spec_from_loader(
                fullname,
                _LegacyPackageLoader(),
                is_package=True,
            )

        if "." not in fullname:
            return None

        package = fullname.split(".", 1)[0]
        if package not in LEGACY_PACKAGES:
            return None

        target_name = _existing_module(_candidate_names(fullname))
        if target_name is None:
            return None

        return importlib.util.spec_from_loader(
            fullname,
            _RootAliasLoader(target_name),
            is_package=False,
        )


def install() -> None:
    """Installe le résolveur une seule fois."""

    if any(isinstance(finder, FlatRootCompatibilityFinder) for finder in sys.meta_path):
        return
    sys.meta_path.insert(0, FlatRootCompatibilityFinder())


__all__ = ["install", "FlatRootCompatibilityFinder"]
