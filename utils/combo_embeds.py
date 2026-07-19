from __future__ import annotations

import discord

from models.archetype import ArchetypeRecord, ArchetypeSummary
from models.combo import ComboRecord, ComboSummary
from utils.text import truncate


RILLIONA_COLOUR = discord.Colour.from_rgb(112, 84, 190)


def build_archetype_embed(
    archetype: ArchetypeRecord,
    *,
    combo_count: int,
) -> discord.Embed:
    embed = discord.Embed(
        title=f"📚 {archetype.name}",
        description=(
            truncate(archetype.description, 3500)
            if archetype.description
            else "Aucune présentation n'a encore été enregistrée."
        ),
        colour=RILLIONA_COLOUR,
    )
    embed.add_field(
        name="Style de jeu",
        value=archetype.playstyle or "Non renseigné",
        inline=True,
    )
    embed.add_field(
        name="Difficulté",
        value=archetype.difficulty or "Non renseignée",
        inline=True,
    )
    embed.add_field(
        name="Combos archivés",
        value=str(combo_count),
        inline=True,
    )
    embed.set_footer(
        text=f"Fiche d'archétype #{archetype.id} • Madame Rilliona"
    )
    return embed


def build_archetype_list_embed(
    archetypes: list[ArchetypeSummary],
) -> discord.Embed:
    if not archetypes:
        description = "Aucun archétype n'est encore enregistré."
    else:
        lines = []
        for item in archetypes[:40]:
            details = []
            if item.playstyle:
                details.append(item.playstyle)
            if item.difficulty:
                details.append(item.difficulty)
            details_text = " • ".join(details) or "Informations à compléter"
            lines.append(
                f"**{item.name}** — {details_text} "
                f"— `{item.combo_count}` combo(s)"
            )
        description = "\n".join(lines)

    embed = discord.Embed(
        title="📖 Catalogue des archétypes",
        description=description,
        colour=RILLIONA_COLOUR,
    )
    embed.set_footer(
        text=f"{len(archetypes)} archétype(s) affiché(s)"
    )
    return embed


def build_combo_embed(combo: ComboRecord) -> discord.Embed:
    embed = discord.Embed(
        title=f"🧠 {combo.name}",
        description=truncate(combo.description, 1800),
        colour=RILLIONA_COLOUR,
    )

    embed.add_field(
        name="Archétype",
        value=combo.archetype_name,
        inline=True,
    )
    embed.add_field(
        name="Format",
        value=combo.game_format,
        inline=True,
    )
    embed.add_field(
        name="Difficulté",
        value=combo.difficulty,
        inline=True,
    )
    embed.add_field(
        name="Type de ligne",
        value=combo.combo_type,
        inline=True,
    )
    embed.add_field(
        name="Banlist de référence",
        value=combo.banlist or "Non précisée",
        inline=True,
    )
    embed.add_field(
        name="Nombre d'étapes",
        value=str(len(combo.steps)),
        inline=True,
    )

    embed.add_field(
        name="Cartes de départ",
        value=truncate(combo.starter_text, 1000),
        inline=False,
    )

    if combo.requirements:
        embed.add_field(
            name="Conditions et prérequis",
            value=truncate(combo.requirements, 1000),
            inline=False,
        )

    embed.add_field(
        name="Terrain final",
        value=truncate(combo.endboard, 1000),
        inline=False,
    )

    if combo.interruptions:
        embed.add_field(
            name="Interactions produites",
            value=truncate(combo.interruptions, 1000),
            inline=False,
        )

    if combo.follow_up:
        embed.add_field(
            name="Follow-up",
            value=truncate(combo.follow_up, 1000),
            inline=False,
        )

    embed.set_footer(
        text=(
            f"Combo #{combo.id} • Ajouté par l'utilisateur "
            f"{combo.author_id} • Madame Rilliona"
        )
    )
    return embed


def build_steps_embed(
    combo: ComboRecord,
    index: int,
) -> discord.Embed:
    step = combo.steps[index]
    embed = discord.Embed(
        title=f"📑 {combo.name}",
        description=step.instruction,
        colour=RILLIONA_COLOUR,
    )
    embed.add_field(
        name="Progression",
        value=f"Étape {index + 1} sur {len(combo.steps)}",
        inline=False,
    )
    embed.set_footer(
        text=f"{combo.archetype_name} • Combo #{combo.id}"
    )
    return embed


def build_analysis_embed(combo: ComboRecord) -> discord.Embed:
    embed = discord.Embed(
        title=f"🔍 Analyse stratégique — {combo.name}",
        colour=RILLIONA_COLOUR,
    )

    embed.add_field(
        name="Faiblesses",
        value=truncate(
            combo.weaknesses or "Aucune faiblesse documentée.",
            1000,
        ),
        inline=False,
    )
    embed.add_field(
        name="Choke points",
        value=truncate(
            combo.choke_points or "Aucun point de rupture documenté.",
            1000,
        ),
        inline=False,
    )
    embed.add_field(
        name="Recovery",
        value=truncate(
            combo.recovery or "Aucune ligne de reprise documentée.",
            1000,
        ),
        inline=False,
    )
    embed.set_footer(
        text=f"{combo.archetype_name} • Combo #{combo.id}"
    )
    return embed


def build_resources_embed(combo: ComboRecord) -> discord.Embed:
    embed = discord.Embed(
        title=f"🗂️ Ressources — {combo.name}",
        colour=RILLIONA_COLOUR,
    )
    embed.add_field(
        name="Starter",
        value=truncate(combo.starter_text, 1000),
        inline=False,
    )
    embed.add_field(
        name="Prérequis",
        value=truncate(
            combo.requirements or "Aucun prérequis supplémentaire.",
            1000,
        ),
        inline=False,
    )
    embed.add_field(
        name="Endboard",
        value=truncate(combo.endboard, 1000),
        inline=False,
    )
    embed.add_field(
        name="Follow-up",
        value=truncate(
            combo.follow_up or "Aucun follow-up documenté.",
            1000,
        ),
        inline=False,
    )
    return embed


def build_combo_list_embed(
    archetype_name: str,
    combos: list[ComboSummary],
) -> discord.Embed:
    if not combos:
        description = "Aucun combo vérifié n'est encore archivé."
    else:
        lines = []
        for combo in combos[:40]:
            lines.append(
                f"**#{combo.id} — {combo.name}**\n"
                f"`{combo.combo_type}` • `{combo.game_format}` • "
                f"`{combo.difficulty}`\n"
                f"Starter : {truncate(combo.starter_text, 140)}"
            )
        description = "\n\n".join(lines)

    embed = discord.Embed(
        title=f"📚 Combos — {archetype_name}",
        description=description,
        colour=RILLIONA_COLOUR,
    )
    embed.set_footer(
        text=f"{len(combos)} combo(s) affiché(s)"
    )
    return embed
