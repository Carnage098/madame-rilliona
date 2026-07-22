from __future__ import annotations

import discord

from models.archetype import Archetype
from models.card import Card
from models.card_knowledge import CardAlias, CardRole
from models.combo import Combo
from utils.text import truncate


PURPLE = discord.Colour.from_rgb(118, 79, 168)


def error_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(
        title=f"❌ {title}",
        description=description,
        colour=discord.Colour.red(),
    )


def success_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(
        title=f"✅ {title}",
        description=description,
        colour=discord.Colour.green(),
    )


def card_embed(card: Card) -> discord.Embed:
    embed = discord.Embed(
        title=card.display_name,
        url=card.ygoprodeck_url,
        description=truncate(card.display_description, 3900),
        colour=PURPLE,
    )
    if card.name_fr and card.name_fr != card.name_en:
        embed.add_field(name="Nom anglais", value=card.name_en, inline=False)
    if card.classification:
        embed.add_field(
            name="Classement",
            value=truncate(card.classification, 1024),
            inline=False,
        )
    elif card.card_type:
        embed.add_field(name="Type", value=card.card_type, inline=True)
    if card.archetype:
        embed.add_field(name="Archétype", value=card.archetype, inline=True)

    stats: list[str] = []
    if card.level is not None:
        stats.append(f"Niveau {card.level}")
    if card.rank is not None:
        stats.append(f"Rang {card.rank}")
    if card.linkval is not None:
        stats.append(f"Lien {card.linkval}")
    if card.scale is not None:
        stats.append(f"Échelle {card.scale}")
    if card.atk is not None:
        stats.append(f"ATK {card.atk}")
    if card.defense is not None:
        stats.append(f"DEF {card.defense}")
    if stats:
        embed.add_field(name="Statistiques", value=" • ".join(stats), inline=False)

    if card.link_markers:
        embed.add_field(
            name="Marqueurs Lien",
            value=" • ".join(card.link_markers),
            inline=False,
        )

    bans: list[str] = []
    if card.ban_tcg:
        bans.append(f"TCG : {card.ban_tcg}")
    if card.ban_ocg:
        bans.append(f"OCG : {card.ban_ocg}")
    if card.ban_goat:
        bans.append(f"GOAT : {card.ban_goat}")
    if bans:
        embed.add_field(name="Banlists", value="\n".join(bans), inline=False)

    embed.set_footer(
        text=(
            f"ID YGOPRODeck : {card.ygoprodeck_id} • "
            f"Source : {card.import_source}"
        )
    )
    return embed



def add_card_knowledge(
    embed: discord.Embed,
    *,
    aliases: list[CardAlias] | tuple[CardAlias, ...] = (),
    roles: list[CardRole] | tuple[CardRole, ...] = (),
) -> discord.Embed:
    """Ajoute les alias et rôles stratégiques sans recréer la fiche de carte."""
    if roles:
        role_lines = []
        for item in roles:
            line = f"• **{item.label}**"
            if item.notes:
                line += f" — {truncate(item.notes, 180)}"
            role_lines.append(line)
        embed.add_field(
            name="Rôles stratégiques",
            value=truncate("\n".join(role_lines), 1024),
            inline=False,
        )
    if aliases:
        embed.add_field(
            name="Alias et surnoms",
            value=truncate(" • ".join(item.alias for item in aliases), 1024),
            inline=False,
        )
    return embed

def archetype_embed(archetype: Archetype) -> discord.Embed:
    embed = discord.Embed(
        title=f"📚 {archetype.name}",
        description=truncate(archetype.presentation, 3900),
        colour=PURPLE,
    )
    embed.add_field(
        name="Style de jeu",
        value=truncate(archetype.play_style, 1024),
        inline=False,
    )
    if archetype.api_name and archetype.api_name.casefold() != archetype.name.casefold():
        embed.add_field(
            name="Nom du catalogue",
            value=archetype.api_name,
            inline=True,
        )
    embed.add_field(name="Difficulté", value=archetype.difficulty, inline=True)
    embed.add_field(
        name="Cartes enregistrées",
        value=str(archetype.card_count),
        inline=True,
    )
    embed.add_field(
        name="Combos archivés",
        value=str(archetype.combo_count),
        inline=True,
    )
    if archetype.cards_synced_at is not None:
        embed.set_footer(
            text=f"Cartes synchronisées le {archetype.cards_synced_at:%d/%m/%Y à %H:%M} UTC"
        )
    return embed


def combo_embed(combo: Combo) -> discord.Embed:
    embed = discord.Embed(
        title=f"🧠 {combo.name}",
        description=truncate(combo.description, 3900),
        colour=PURPLE,
    )
    embed.add_field(name="Archétype", value=combo.archetype_name, inline=True)
    embed.add_field(name="Format", value=combo.game_format, inline=True)
    embed.add_field(name="Difficulté", value=combo.difficulty, inline=True)
    embed.add_field(name="Type de ligne", value=combo.line_type, inline=True)
    if combo.banlist:
        embed.add_field(
            name="Banlist",
            value=truncate(combo.banlist, 1024),
            inline=True,
        )
    embed.set_footer(text=f"Combo ID : {combo.id} • {len(combo.steps)} étape(s)")
    return embed
