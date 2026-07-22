from __future__ import annotations

import runpy
import sys
from pathlib import Path

from flat_import_compat import install


ROOT = Path(__file__).resolve().parent
BOT_FILE = ROOT / "bot.py"


def main() -> None:
    install()

    if not BOT_FILE.is_file():
        raise FileNotFoundError(
            "bot.py est introuvable. start.py doit être placé à la même racine que bot.py."
        )

    # Garantit que les modules placés à la racine sont prioritaires.
    root_text = str(ROOT)
    if root_text not in sys.path:
        sys.path.insert(0, root_text)

    runpy.run_path(str(BOT_FILE), run_name="__main__")


if __name__ == "__main__":
    main()
