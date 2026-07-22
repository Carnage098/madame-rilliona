from __future__ import annotations

import discord


def is_staff_member(
    user: discord.abc.User,
    *,
    configured_role_ids: tuple[int, ...] = (),
) -> bool:
    """Retourne True si le membre a une permission staff ou un rôle configuré."""
    if not isinstance(user, discord.Member):
        return False

    permissions = user.guild_permissions
    if permissions.administrator or permissions.manage_guild or permissions.manage_messages:
        return True

    role_ids = {role.id for role in user.roles}
    return any(role_id in role_ids for role_id in configured_role_ids)
