from __future__ import annotations

import re


def truncate(value: str | None, maximum: int, fallback: str = "Non renseigné") -> str:
    text = (value or "").strip() or fallback
    if len(text) <= maximum:
        return text
    return text[: maximum - 1].rstrip() + "…"


def parse_steps(value: str) -> list[str]:
    steps: list[str] = []
    for line in value.splitlines():
        cleaned = re.sub(r"^\s*\d+[.)-]?\s*", "", line).strip()
        if cleaned:
            steps.append(cleaned)
    return steps


def parse_analysis(value: str) -> tuple[str, str, str]:
    sections = {"weaknesses": [], "choke_points": [], "recovery": []}
    current = "weaknesses"
    for raw_line in value.splitlines():
        line = raw_line.strip()
        lowered = line.lower()
        if lowered.startswith(("faiblesses:", "faiblesse:")):
            current = "weaknesses"
            line = line.split(":", 1)[1].strip()
        elif lowered.startswith(("choke points:", "choke point:", "interruptions:")):
            current = "choke_points"
            line = line.split(":", 1)[1].strip()
        elif lowered.startswith(("recovery:", "récupération:", "recuperation:")):
            current = "recovery"
            line = line.split(":", 1)[1].strip()
        if line:
            sections[current].append(line)
    return (
        "\n".join(sections["weaknesses"]),
        "\n".join(sections["choke_points"]),
        "\n".join(sections["recovery"]),
    )
