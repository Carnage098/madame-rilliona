"""Contrôle statique des imports de Madame Rilliona, sans connexion externe."""
from __future__ import annotations

import importlib

MODULES = (
    "config",
    "database_manager",
    "models.card",
    "models.card_submission",
    "models.archetype",
    "models.combo",
    "repositories.card_repository",
    "repositories.card_submission_repository",
    "repositories.archetype_repository",
    "repositories.combo_repository",
    "services.card_api_service",
    "services.card_catalog_service",
    "services.card_image_service",
    "services.card_import_service",
    "services.card_submission_service",
    "services.combo_service",
    "utils.permissions",
    "views.card_submission_review",
    "cogs.cards",
    "cogs.card_admin",
    "cogs.archetypes",
    "cogs.combos",
    "bot",
)


def main() -> None:
    for module_name in MODULES:
        importlib.import_module(module_name)
        print(f"OK  {module_name}")
    print("Tous les imports de Madame Rilliona sont valides.")


if __name__ == "__main__":
    main()
