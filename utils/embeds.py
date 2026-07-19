from __future__ import annotations

import discord

from models.card import CardRecord
from utils.text import truncate


RILLIONA_COLOUR = discord.Colour.from_rgb(112, 84, 190)


def build_card_embed(card: CardRecord) -> discord.Embed:
    embed = discord.Embed(
        title=card.display_name,
        description=truncate(card.display_description, 3500),
        colour=RILLIONA_COLOUR,
        url=card.ygoprodeck_url,
    )

    type_parts = [card.display_type]
    if card.display_race:
        type_parts.append(card.display_race)

    embed.add_field(
        name="Type",
        value=" • ".join(type_parts),
        inline=False,
    )

    monster_stats: list[str] = []
    if card.attribute:
        monster_stats.append(f"**Attribut :** {card.attribute}")
    if card.level is not None:
        monster_stats.append(f"**Niveau/Rang :** {card.level}")
    if card.link_value is not None:
        monster_stats.append(f"**Lien :** {card.link_value}")
    if card.scale is not None:
        monster_stats.append(f"**Échelle Pendule :** {card.scale}")
    if card.attack is not None:
        monster_stats.append(f"**ATK :** {card.attack}")
    if card.defense is not None:
        monster_stats.append(f"**DEF :** {card.defense}")

    if monster_stats:
        embed.add_field(
            name="Caractéristiques",
            value="\n".join(monster_stats),
            inline=True,
        )

    if card.display_archetype:
        embed.add_field(
            name="Archétype",
            value=card.display_archetype,
            inline=True,
        )

    banlist_lines = []
    if card.ban_tcg:
        banlist_lines.append(f"**TCG :** {card.ban_tcg}")
    if card.ban_ocg:
        banlist_lines.append(f"**OCG :** {card.ban_ocg}")
    if card.ban_goat:
        banlist_lines.append(f"**GOAT :** {card.ban_goat}")

    if banlist_lines:
        embed.add_field(
            name="Restrictions",
            value="\n".join(banlist_lines),
            inline=False,
        )

    if card.link_markers:
        embed.add_field(
            name="Flèches Lien",
            value=", ".join(card.link_markers),
            inline=False,
        )

    embed.set_footer(
        text=(
            f"Identifiant YGOPRODeck : {card.ygoprodeck_id} "
            "• Catalogue de Madame Rilliona"
        )
    )
    return embed
