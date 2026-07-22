from __future__ import annotations

import discord

from models.archetype import Archetype
from models.card import Card
from models.combo import Combo
from utils.text import truncate


PURPLE = discord.Colour.from_rgb(118, 79, 168)


def error_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=f"❌ {title}", description=description, colour=discord.Colour.red())


def success_embed(title: str, description: str) -> discord.Embed:
    return discord.Embed(title=f"✅ {title}", description=description, colour=discord.Colour.green())


def card_embed(card: Card) -> discord.Embed:
    embed = discord.Embed(
        title=card.display_name,
        description=truncate(card.display_description, 3900),
        colour=PURPLE,
    )
    if card.name_fr and card.name_fr != card.name_en:
        embed.add_field(name="Nom anglais", value=card.name_en, inline=False)
    if card.card_type:
        embed.add_field(name="Type", value=card.card_type, inline=True)
    if card.race:
        embed.add_field(name="Race", value=card.race, inline=True)
    if card.archetype:
        embed.add_field(name="Archétype", value=card.archetype, inline=True)
    stats = []
    if card.attribute:
        stats.append(card.attribute)
    if card.level is not None:
        stats.append(f"Niveau {card.level}")
    if card.rank is not None:
        stats.append(f"Rang {card.rank}")
    if card.linkval is not None:
        stats.append(f"Lien {card.linkval}")
    if card.atk is not None:
        stats.append(f"ATK {card.atk}")
    if card.defense is not None:
        stats.append(f"DEF {card.defense}")
    if stats:
        embed.add_field(name="Statistiques", value=" • ".join(stats), inline=False)
    embed.set_footer(text=f"ID YGOPRODeck : {card.ygoprodeck_id}")
    return embed


def archetype_embed(archetype: Archetype) -> discord.Embed:
    embed = discord.Embed(
        title=f"📚 {archetype.name}",
        description=truncate(archetype.presentation, 3900),
        colour=PURPLE,
    )
    embed.add_field(name="Style de jeu", value=truncate(archetype.play_style, 1024), inline=False)
    embed.add_field(name="Difficulté", value=archetype.difficulty, inline=True)
    embed.add_field(name="Combos archivés", value=str(archetype.combo_count), inline=True)
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
        embed.add_field(name="Banlist", value=truncate(combo.banlist, 1024), inline=True)
    embed.set_footer(text=f"Combo ID : {combo.id} • {len(combo.steps)} étape(s)")
    return embed
