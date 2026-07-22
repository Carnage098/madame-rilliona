from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from config import SETTINGS
from models.card_submission import CardSubmission
from models.card_knowledge import ROLE_LABELS, role_label
from utils.embeds import add_card_knowledge, card_embed, error_embed, success_embed
from utils.permissions import is_staff_member
from views.card_submission_review import (
    CardSubmissionReviewView,
    duplicate_summary,
    submission_embed,
)


LOGGER = logging.getLogger(__name__)


ROLE_CHOICES = [
    app_commands.Choice(name=label, value=value)
    for value, label in ROLE_LABELS.items()
]



class CardCog(
    commands.GroupCog,
    group_name="carte",
    group_description="Consulter le catalogue de cartes",
):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    async def _require_staff(self, interaction: discord.Interaction) -> bool:
        if is_staff_member(
            interaction.user,
            configured_role_ids=SETTINGS.staff_role_ids,
        ):
            return True
        message = (
            "Cette commande est réservée au staff : Administrateur, "
            "Gérer le serveur, Gérer les messages ou rôle configuré dans STAFF_ROLE_IDS."
        )
        if interaction.response.is_done():
            await interaction.followup.send(
                embed=error_embed("Permission refusée", message),
                ephemeral=True,
            )
        else:
            await interaction.response.send_message(
                embed=error_embed("Permission refusée", message),
                ephemeral=True,
            )
        return False

    async def category_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        del self, interaction
        values = ("Monstre", "Magie", "Piège", "Compétence", "Jeton", "Autre")
        query = current.casefold().strip()
        return [
            app_commands.Choice(name=value, value=value)
            for value in values
            if not query or query in value.casefold()
        ][:25]

    async def section_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        del self, interaction
        values = ("Main Deck", "Extra Deck", "Zone Magie/Piège", "Hors Deck principal")
        query = current.casefold().strip()
        return [
            app_commands.Choice(name=value, value=value)
            for value in values
            if not query or query in value.casefold()
        ][:25]

    async def attribute_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        del self, interaction
        values = ("DARK", "LIGHT", "EARTH", "WATER", "FIRE", "WIND", "DIVINE")
        query = current.casefold().strip()
        return [
            app_commands.Choice(name=value, value=value)
            for value in values
            if not query or query in value.casefold()
        ][:25]

    async def role_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        del self, interaction
        query = current.casefold().strip()
        return [
            app_commands.Choice(name=label, value=value)
            for value, label in ROLE_LABELS.items()
            if not query or query in label.casefold() or query in value.casefold()
        ][:25]

    async def card_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ):
        del interaction
        try:
            suggestions = await self.bot.card_catalog_service.autocomplete(current)
        except Exception:
            LOGGER.exception("Échec de l'autocomplétion pour %r", current)
            suggestions = []

        return [
            app_commands.Choice(
                name=suggestion.display_name[:100],
                value=str(suggestion.card_id),
            )
            for suggestion in suggestions[:25]
        ]

    async def _post_review_message(self, submission: CardSubmission) -> bool:
        channel_id = SETTINGS.card_review_channel_id
        if channel_id is None:
            return False

        try:
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                channel = await self.bot.fetch_channel(channel_id)
            if not hasattr(channel, "send"):
                raise TypeError("Le salon configuré ne permet pas l'envoi de messages.")

            embed = submission_embed(submission)
            view = CardSubmissionReviewView(self.bot, submission.id)
            file: discord.File | None = None
            if (
                submission.pending_image_path is not None
                and submission.pending_image_path.is_file()
            ):
                filename = f"proposition_{submission.id}.png"
                file = discord.File(submission.pending_image_path, filename=filename)
                embed.set_image(url=f"attachment://{filename}")

            if file is None:
                message = await channel.send(embed=embed, view=view)
            else:
                message = await channel.send(embed=embed, view=view, file=file)

            await self.bot.card_submission_repository.set_review_message(
                submission.id,
                channel_id=message.channel.id,
                message_id=message.id,
            )
            return True
        except (discord.Forbidden, discord.NotFound, discord.HTTPException, TypeError):
            LOGGER.exception(
                "Impossible d'envoyer la proposition %s dans le salon de validation",
                submission.id,
            )
            return False

    @app_commands.command(name="rechercher", description="Rechercher une carte Yu-Gi-Oh!")
    @app_commands.describe(carte="Nom français, nom anglais ou identifiant de la carte")
    @app_commands.autocomplete(carte=card_autocomplete)
    async def search_card(
        self,
        interaction: discord.Interaction,
        carte: str,
    ) -> None:
        await interaction.response.defer(thinking=True)

        try:
            card = await self.bot.card_catalog_service.find_or_fetch(carte)
        except Exception:
            LOGGER.exception("Échec de la recherche de carte pour %r", carte)
            await interaction.followup.send(
                embed=error_embed(
                    "Recherche temporairement indisponible",
                    "La base externe n'a pas répondu correctement. Réessaie dans quelques instants.",
                ),
                ephemeral=True,
            )
            return

        if card is None:
            await interaction.followup.send(
                embed=error_embed(
                    "Carte introuvable",
                    "Vérifie l'orthographe du nom français ou anglais.",
                ),
                ephemeral=True,
            )
            return

        aliases = await self.bot.card_knowledge_repository.list_aliases(
            card.ygoprodeck_id
        )
        roles = await self.bot.card_knowledge_repository.list_roles(
            card.ygoprodeck_id
        )
        embed = add_card_knowledge(
            card_embed(card),
            aliases=aliases,
            roles=roles,
        )
        try:
            image_path = await self.bot.card_image_service.get(card)
        except Exception:
            LOGGER.exception(
                "Impossible de récupérer l'image de la carte %s",
                card.ygoprodeck_id,
            )
            image_path = None

        if image_path:
            file = discord.File(image_path, filename=image_path.name)
            embed.set_image(url=f"attachment://{image_path.name}")
            await interaction.followup.send(embed=embed, file=file)
        else:
            if card.image_url:
                embed.set_image(url=card.image_url)
            await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="proposer",
        description="Proposer une carte au staff depuis un site ou une image PNG",
    )
    @app_commands.guild_only()
    @app_commands.describe(
        source="Choisir entre une URL et une image PNG",
        nom="Nom français/anglais ou ID, conseillé pour un PNG",
        url="Page de la carte ou URL de référence",
        image="Image PNG de la carte",
    )
    @app_commands.choices(
        source=[
            app_commands.Choice(name="Site internet", value="url"),
            app_commands.Choice(name="Image PNG", value="png"),
        ]
    )
    async def propose_card(
        self,
        interaction: discord.Interaction,
        source: app_commands.Choice[str],
        nom: str | None = None,
        url: str | None = None,
        image: discord.Attachment | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            if source.value == "url":
                if not url:
                    raise ValueError("Renseigne l'option `url`.")
                if image is not None:
                    raise ValueError("N'envoie pas d'image avec la source Site internet.")
                submission = await self.bot.card_submission_service.submit_from_url(
                    url=url,
                    name_hint=nom,
                    submitted_by=interaction.user.id,
                    guild_id=interaction.guild_id,
                )
            elif source.value == "png":
                if image is None:
                    raise ValueError("Ajoute un fichier dans l'option `image`.")
                if url:
                    raise ValueError("Ne renseigne pas d'URL avec la source Image PNG.")
                if image.size > SETTINGS.max_staff_image_bytes:
                    maximum = SETTINGS.max_staff_image_bytes / (1024 * 1024)
                    raise ValueError(f"L'image dépasse la limite de {maximum:.1f} Mo.")
                content = await image.read(use_cached=True)
                submission = await self.bot.card_submission_service.submit_from_png(
                    content=content,
                    filename=image.filename,
                    content_type=image.content_type,
                    declared_size=image.size,
                    name_hint=nom,
                    submitted_by=interaction.user.id,
                    guild_id=interaction.guild_id,
                )
            else:
                raise ValueError("La source sélectionnée n'est pas reconnue.")
        except ValueError as error:
            await interaction.followup.send(
                embed=error_embed("Proposition impossible", str(error)),
                ephemeral=True,
            )
            return
        except discord.HTTPException as error:
            await interaction.followup.send(
                embed=error_embed(
                    "Image inaccessible",
                    f"Discord n'a pas permis de lire le fichier : {error}",
                ),
                ephemeral=True,
            )
            return
        except Exception:
            LOGGER.exception("Échec de la proposition d'une carte")
            await interaction.followup.send(
                embed=error_embed(
                    "Proposition temporairement indisponible",
                    "La carte n'a pas pu être préparée. Réessaie dans quelques instants.",
                ),
                ephemeral=True,
            )
            return

        posted = await self._post_review_message(submission)
        review_location = (
            f"Elle a été transmise dans <#{SETTINGS.card_review_channel_id}>."
            if posted and SETTINGS.card_review_channel_id is not None
            else (
                "Elle est enregistrée dans la file d'attente. Le staff peut l'ouvrir "
                "avec `/base examiner_demande`."
            )
        )
        await interaction.followup.send(
            embed=success_embed(
                "Proposition enregistrée",
                f"**Demande #{submission.id} — {submission.candidate.display_name}**\n\n"
                "La carte n'a pas encore été ajoutée au catalogue. "
                f"{review_location}\n\n"
                f"**Contrôle des doublons**\n{duplicate_summary(submission.duplicates)}",
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="definir_role",
        description="Attribuer un rôle stratégique à une carte (staff)",
    )
    @app_commands.describe(
        carte="Nom, alias ou identifiant de la carte",
        role="Fonction de la carte dans un deck",
        notes="Explication facultative du rôle",
    )
    @app_commands.autocomplete(carte=card_autocomplete)
    @app_commands.choices(role=ROLE_CHOICES)
    async def define_role(
        self,
        interaction: discord.Interaction,
        carte: str,
        role: app_commands.Choice[str],
        notes: str | None = None,
    ) -> None:
        if not await self._require_staff(interaction):
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        card = await self.bot.card_catalog_service.find_or_fetch(carte)
        if card is None:
            await interaction.followup.send(
                embed=error_embed("Carte introuvable", "Vérifie son nom ou son identifiant."),
                ephemeral=True,
            )
            return
        try:
            assigned = await self.bot.card_knowledge_repository.set_role(
                card_id=card.ygoprodeck_id,
                role=role.value,
                notes=notes,
                assigned_by=interaction.user.id,
            )
        except ValueError as error:
            await interaction.followup.send(
                embed=error_embed("Rôle impossible", str(error)),
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            embed=success_embed(
                "Rôle enregistré",
                f"**{card.display_name}** est maintenant classée comme **{assigned.label}**."
                + (f"\nNotes : {assigned.notes}" if assigned.notes else ""),
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="retirer_role",
        description="Retirer un rôle stratégique d'une carte (staff)",
    )
    @app_commands.autocomplete(carte=card_autocomplete)
    @app_commands.choices(role=ROLE_CHOICES)
    async def remove_role(
        self,
        interaction: discord.Interaction,
        carte: str,
        role: app_commands.Choice[str],
    ) -> None:
        if not await self._require_staff(interaction):
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        card = await self.bot.card_catalog_service.find_or_fetch(carte)
        if card is None:
            await interaction.followup.send(
                embed=error_embed("Carte introuvable", "Vérifie son nom ou son identifiant."),
                ephemeral=True,
            )
            return
        removed = await self.bot.card_knowledge_repository.remove_role(
            card_id=card.ygoprodeck_id,
            role=role.value,
        )
        if not removed:
            await interaction.followup.send(
                embed=error_embed(
                    "Rôle absent",
                    f"**{card.display_name}** ne possédait pas le rôle **{role_label(role.value)}**.",
                ),
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            embed=success_embed(
                "Rôle retiré",
                f"Le rôle **{role_label(role.value)}** a été retiré de **{card.display_name}**.",
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="ajouter_alias",
        description="Ajouter un surnom ou une autre traduction à une carte (staff)",
    )
    @app_commands.describe(
        carte="Nom, alias ou identifiant de la carte",
        alias="Surnom, abréviation ou autre traduction",
        langue="Langue ou origine facultative : FR, EN, JP, communauté…",
    )
    @app_commands.autocomplete(carte=card_autocomplete)
    async def add_alias(
        self,
        interaction: discord.Interaction,
        carte: str,
        alias: str,
        langue: str | None = None,
    ) -> None:
        if not await self._require_staff(interaction):
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        card = await self.bot.card_catalog_service.find_or_fetch(carte)
        if card is None:
            await interaction.followup.send(
                embed=error_embed("Carte introuvable", "Vérifie son nom ou son identifiant."),
                ephemeral=True,
            )
            return
        try:
            entry = await self.bot.card_knowledge_repository.add_alias(
                card_id=card.ygoprodeck_id,
                alias=alias,
                language=langue,
                source="staff",
                created_by=interaction.user.id,
            )
        except ValueError as error:
            await interaction.followup.send(
                embed=error_embed("Alias impossible", str(error)),
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            embed=success_embed(
                "Alias enregistré",
                f"`{entry.alias}` permet maintenant de retrouver **{card.display_name}**.",
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="retirer_alias",
        description="Retirer un alias d'une carte (staff)",
    )
    @app_commands.autocomplete(carte=card_autocomplete)
    async def remove_alias(
        self,
        interaction: discord.Interaction,
        carte: str,
        alias: str,
    ) -> None:
        if not await self._require_staff(interaction):
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        card = await self.bot.card_catalog_service.find_or_fetch(carte)
        if card is None:
            await interaction.followup.send(
                embed=error_embed("Carte introuvable", "Vérifie son nom ou son identifiant."),
                ephemeral=True,
            )
            return
        removed = await self.bot.card_knowledge_repository.remove_alias(
            card_id=card.ygoprodeck_id,
            alias=alias,
        )
        if not removed:
            await interaction.followup.send(
                embed=error_embed("Alias absent", "Cet alias n'était pas associé à cette carte."),
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            embed=success_embed(
                "Alias retiré",
                f"`{alias}` n'est plus associé à **{card.display_name}**.",
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="filtrer",
        description="Rechercher des cartes par effet, statistiques, type ou rôle",
    )
    @app_commands.describe(
        archetype="Nom ou partie du nom de l'archétype",
        categorie="Monstre, Magie, Piège…",
        section="Main Deck, Extra Deck…",
        attribut="Attribut du monstre",
        type_monstre="Dragon, Magicien, Guerrier…",
        texte_effet="Texte à retrouver dans l'effet français ou anglais",
        role="Rôle stratégique attribué par le staff",
        atk_min="ATK minimale",
        atk_max="ATK maximale",
        niveau="Niveau exact",
        rang="Rang exact",
        lien="Valeur Lien exacte",
        limite="Nombre maximal de résultats",
    )
    @app_commands.autocomplete(
        categorie=category_autocomplete,
        section=section_autocomplete,
        attribut=attribute_autocomplete,
        role=role_autocomplete,
    )
    async def filter_cards(
        self,
        interaction: discord.Interaction,
        archetype: str | None = None,
        categorie: str | None = None,
        section: str | None = None,
        attribut: str | None = None,
        type_monstre: str | None = None,
        texte_effet: str | None = None,
        role: str | None = None,
        atk_min: int | None = None,
        atk_max: int | None = None,
        niveau: int | None = None,
        rang: int | None = None,
        lien: int | None = None,
        limite: app_commands.Range[int, 1, 25] = 10,
    ) -> None:
        await interaction.response.defer(thinking=True)
        if atk_min is not None and atk_max is not None and atk_min > atk_max:
            await interaction.followup.send(
                embed=error_embed("Filtres invalides", "ATK minimale ne peut pas dépasser ATK maximale."),
                ephemeral=True,
            )
            return
        try:
            cards = await self.bot.card_knowledge_repository.advanced_search(
                archetype=archetype,
                category=categorie,
                deck_section=section,
                attribute=attribut,
                race=type_monstre,
                effect_text=texte_effet,
                role=role,
                min_atk=atk_min,
                max_atk=atk_max,
                level=niveau,
                rank=rang,
                linkval=lien,
                limit=int(limite),
            )
        except ValueError as error:
            await interaction.followup.send(
                embed=error_embed("Recherche impossible", str(error)),
                ephemeral=True,
            )
            return
        if not cards:
            await interaction.followup.send(
                embed=error_embed("Aucun résultat", "Aucune carte locale ne correspond à ces filtres."),
                ephemeral=True,
            )
            return

        roles_by_card = await self.bot.card_knowledge_repository.roles_for_cards(
            [card.ygoprodeck_id for card in cards]
        )
        lines: list[str] = []
        for card in cards:
            roles = roles_by_card.get(card.ygoprodeck_id, [])
            role_text = ", ".join(item.label for item in roles) or "aucun rôle"
            details = card.classification or card.card_type or "non classée"
            lines.append(
                f"• **{card.display_name}** (`{card.ygoprodeck_id}`)\n"
                f"  {details} • {role_text}"
            )
        embed = discord.Embed(
            title="🔎 Recherche avancée",
            description="\n".join(lines)[:4000],
            colour=discord.Colour.purple(),
        )
        embed.set_footer(text=f"{len(cards)} résultat(s) affiché(s) depuis PostgreSQL")
        await interaction.followup.send(embed=embed)

    @app_commands.command(
        name="archetype",
        description="Lister les cartes d'un archétype et les importer si nécessaire",
    )
    async def cards_by_archetype(
        self,
        interaction: discord.Interaction,
        nom: str,
    ) -> None:
        await interaction.response.defer(thinking=True)

        entry = await self.bot.archetype_repository.get_by_name(nom)
        catalogue_name = entry.catalogue_name if entry else nom
        cards = await self.bot.card_repository.list_by_archetype(catalogue_name)

        if not cards:
            try:
                sync = await self.bot.card_catalog_service.synchronize_archetype(
                    catalogue_name
                )
                catalogue_name = sync.canonical_name
                cards = await self.bot.card_repository.list_by_archetype(
                    catalogue_name
                )
                if entry is not None:
                    await self.bot.archetype_repository.mark_cards_synced(
                        entry.id,
                        api_name=sync.canonical_name,
                    )
            except ValueError as error:
                await interaction.followup.send(
                    embed=error_embed("Archétype introuvable", str(error)),
                    ephemeral=True,
                )
                return
            except Exception:
                LOGGER.exception(
                    "Échec de l'import automatique de l'archétype %r",
                    catalogue_name,
                )
                await interaction.followup.send(
                    embed=error_embed(
                        "Import impossible",
                        "La base externe n'a pas répondu correctement.",
                    ),
                    ephemeral=True,
                )
                return

        if not cards:
            await interaction.followup.send(
                embed=error_embed(
                    "Aucune carte",
                    "Aucune carte n'a été trouvée pour cet archétype.",
                ),
                ephemeral=True,
            )
            return

        lines: list[str] = []
        for card in cards:
            category = card.card_category or "Non classée"
            section = card.deck_section or "Section inconnue"
            lines.append(
                f"• **{card.display_name}** — {category} / {section} (`{card.ygoprodeck_id}`)"
            )

        description = ""
        displayed = 0
        for line in lines:
            candidate = f"{description}\n{line}" if description else line
            if len(candidate) > 3900:
                break
            description = candidate
            displayed += 1

        total = await self.bot.card_repository.count_by_archetype(catalogue_name)
        if displayed < total:
            description += f"\n\n… et **{total - displayed}** autre(s) carte(s) enregistrée(s)."

        embed = discord.Embed(
            title=f"🎴 Cartes — {catalogue_name}",
            description=description,
            colour=discord.Colour.purple(),
        )
        embed.set_footer(
            text=f"{total} carte(s) enregistrée(s) • {displayed} affichée(s)"
        )
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CardCog(bot))
