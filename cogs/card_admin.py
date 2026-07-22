from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands

from config import SETTINGS
from models.card_submission import CardSubmission
from utils.embeds import card_embed, error_embed, success_embed
from utils.permissions import is_staff_member
from views.card_submission_review import CardSubmissionReviewView, submission_embed


LOGGER = logging.getLogger(__name__)


class CardAdminCog(
    commands.GroupCog,
    group_name="base",
    group_description="Administration de la base",
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
            "Cette commande est réservée au staff. Il faut avoir la permission "
            "**Gérer le serveur**, **Gérer les messages**, **Administrateur**, "
            "ou un rôle configuré dans `STAFF_ROLE_IDS`."
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

    async def local_card_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        del interaction
        cards = await self.bot.card_repository.autocomplete(current, limit=25)
        return [
            app_commands.Choice(
                name=(
                    f"{card.display_name} — {card.name_en}"
                    if card.name_fr and card.name_fr.casefold() != card.name_en.casefold()
                    else card.display_name
                )[:100],
                value=str(card.ygoprodeck_id),
            )
            for card in cards[:25]
        ]

    async def _send_card_with_image(
        self,
        interaction: discord.Interaction,
        *,
        embed: discord.Embed,
        card: object,
    ) -> None:
        try:
            image_path = await self.bot.card_image_service.get(card)
        except Exception:
            LOGGER.exception("Impossible de préparer l'image de la carte")
            image_path = None

        if image_path is not None:
            filename = f"{getattr(card, 'ygoprodeck_id')}{image_path.suffix.lower()}"
            file = discord.File(image_path, filename=filename)
            embed.set_image(url=f"attachment://{filename}")
            await interaction.followup.send(
                embed=embed,
                file=file,
                ephemeral=True,
            )
            return

        image_url = getattr(card, "image_url", None)
        if image_url:
            embed.set_image(url=image_url)
        await interaction.followup.send(embed=embed, ephemeral=True)

    async def _send_submission_review(
        self,
        interaction: discord.Interaction,
        submission: CardSubmission,
    ) -> None:
        embed = submission_embed(submission)
        view = CardSubmissionReviewView(
            self.bot,
            submission.id,
            disabled=submission.status != "pending",
        )
        image_path = submission.pending_image_path
        if image_path is not None and image_path.is_file():
            filename = f"proposition_{submission.id}.png"
            file = discord.File(image_path, filename=filename)
            embed.set_image(url=f"attachment://{filename}")
            await interaction.followup.send(
                embed=embed,
                view=view,
                file=file,
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            embed=embed,
            view=view,
            ephemeral=True,
        )

    @app_commands.command(name="statut", description="Afficher l'état du catalogue de cartes")
    async def catalogue_status(self, interaction: discord.Interaction) -> None:
        count = await self.bot.card_repository.count()
        pending_submissions = await self.bot.card_submission_repository.count_pending()
        categories = await self.bot.card_repository.category_counts()
        category_lines = "\n".join(
            f"• **{name}** : {total}"
            for name, total in categories.items()
        ) or "• Aucune carte classée"
        discovery_status = (
            f"active, une découverte environ toutes les "
            f"{SETTINGS.random_discovery_interval_minutes} minutes"
            if SETTINGS.random_discovery_enabled
            else "désactivée"
        )
        description = (
            f"**{count}** carte(s) enregistrée(s).\n"
            f"**{pending_submissions}** proposition(s) en attente.\n\n"
            f"**Classement**\n{category_lines}\n\n"
            f"**Découverte aléatoire** : {discovery_status}.\n"
            "Toute carte trouvée par `/carte rechercher` est enregistrée automatiquement."
        )
        await interaction.response.send_message(
            embed=success_embed("État du catalogue", description),
            ephemeral=True,
        )

    @app_commands.command(
        name="ajouter_carte",
        description="Ajouter immédiatement une carte (staff uniquement)",
    )
    @app_commands.describe(
        source="Choisir entre une URL et une image PNG",
        nom="Nom français/anglais ou ID de la carte, conseillé pour un PNG",
        url="Page de la carte ou URL de référence",
        image="Image PNG de la carte",
    )
    @app_commands.choices(
        source=[
            app_commands.Choice(name="Site internet", value="url"),
            app_commands.Choice(name="Image PNG", value="png"),
        ]
    )
    async def add_card(
        self,
        interaction: discord.Interaction,
        source: app_commands.Choice[str],
        nom: str | None = None,
        url: str | None = None,
        image: discord.Attachment | None = None,
    ) -> None:
        if not await self._require_staff(interaction):
            return

        await interaction.response.defer(ephemeral=True, thinking=True)

        try:
            if source.value == "url":
                if not url:
                    raise ValueError("Renseigne l'option `url` pour un ajout par site internet.")
                if image is not None:
                    raise ValueError("N'envoie pas d'image lorsque la source choisie est un site internet.")
                result = await self.bot.card_import_service.import_from_url(
                    url=url,
                    name_hint=nom,
                    submitted_by=interaction.user.id,
                )
            elif source.value == "png":
                if image is None:
                    raise ValueError("Ajoute un fichier dans l'option `image`.")
                if url:
                    raise ValueError("Ne renseigne pas d'URL lorsque la source choisie est une image PNG.")
                if image.size > SETTINGS.max_staff_image_bytes:
                    max_mb = SETTINGS.max_staff_image_bytes / (1024 * 1024)
                    raise ValueError(f"L'image dépasse la limite de {max_mb:.1f} Mo.")
                content = await image.read(use_cached=True)
                result = await self.bot.card_import_service.import_from_png(
                    content=content,
                    filename=image.filename,
                    content_type=image.content_type,
                    declared_size=image.size,
                    name_hint=nom,
                    submitted_by=interaction.user.id,
                )
            else:
                raise ValueError("La source sélectionnée n'est pas reconnue.")
        except ValueError as error:
            await interaction.followup.send(
                embed=error_embed("Ajout impossible", str(error)),
                ephemeral=True,
            )
            return
        except discord.HTTPException as error:
            LOGGER.exception("Lecture de la pièce jointe impossible")
            await interaction.followup.send(
                embed=error_embed(
                    "Image inaccessible",
                    f"Discord n'a pas permis de lire le fichier : {error}",
                ),
                ephemeral=True,
            )
            return
        except Exception:
            LOGGER.exception("Échec de l'ajout staff d'une carte")
            await interaction.followup.send(
                embed=error_embed(
                    "Ajout temporairement indisponible",
                    "La carte n'a pas pu être ajoutée. Vérifie la source puis réessaie.",
                ),
                ephemeral=True,
            )
            return

        embed = card_embed(result.card)
        embed.title = f"✅ Carte ajoutée — {result.card.display_name}"
        embed.add_field(
            name="Vérification PostgreSQL",
            value=result.verification.summary,
            inline=False,
        )
        embed.add_field(
            name="Import",
            value=(
                f"Type : **{result.source_type.upper()}**\n"
                f"Journal d'import : **#{result.import_log_id}**\n"
                f"Vérification : **{'réussie' if result.verification.verified else 'incomplète'}**"
            ),
            inline=False,
        )
        await self._send_card_with_image(
            interaction,
            embed=embed,
            card=result.card,
        )

    @app_commands.command(
        name="verifier_carte",
        description="Vérifier qu'une carte est bien enregistrée et complète dans PostgreSQL",
    )
    @app_commands.describe(carte="Nom français, nom anglais ou identifiant")
    @app_commands.autocomplete(carte=local_card_autocomplete)
    async def verify_card(
        self,
        interaction: discord.Interaction,
        carte: str,
    ) -> None:
        if not await self._require_staff(interaction):
            return
        await interaction.response.defer(ephemeral=True, thinking=True)

        verification = await self.bot.card_import_service.verify_local_query(carte)
        if verification is None or verification.card is None:
            await interaction.followup.send(
                embed=error_embed(
                    "Carte absente",
                    "Cette carte n'est pas présente dans la base locale de Madame Rilliona.",
                ),
                ephemeral=True,
            )
            return

        embed = card_embed(verification.card)
        embed.title = (
            f"✅ Vérification réussie — {verification.card.display_name}"
            if verification.verified
            else f"⚠️ Fiche incomplète — {verification.card.display_name}"
        )
        embed.add_field(
            name="Contrôle de la base",
            value=verification.summary,
            inline=False,
        )
        await self._send_card_with_image(
            interaction,
            embed=embed,
            card=verification.card,
        )

    @app_commands.command(
        name="demandes",
        description="Lister les propositions de cartes en attente",
    )
    async def pending_submissions(self, interaction: discord.Interaction) -> None:
        if not await self._require_staff(interaction):
            return
        submissions = await self.bot.card_submission_repository.list_pending(limit=25)
        if not submissions:
            await interaction.response.send_message(
                embed=success_embed(
                    "File de validation vide",
                    "Aucune proposition de carte n'est en attente.",
                ),
                ephemeral=True,
            )
            return

        lines: list[str] = []
        for submission in submissions:
            duplicate_note = {
                "exact_id": "⚠️ même ID",
                "exact_name": "⚠️ même nom",
                "similar": "🔎 nom proche",
                "none": "✅ aucun doublon",
            }.get(submission.duplicate_status, submission.duplicate_status)
            lines.append(
                f"• **#{submission.id}** — {submission.candidate.display_name} "
                f"(`{submission.candidate.ygoprodeck_id}`) — {duplicate_note}"
            )

        embed = discord.Embed(
            title="🗂️ Propositions en attente",
            description="\n".join(lines),
            colour=discord.Colour.orange(),
        )
        embed.set_footer(
            text="Utilise /base examiner_demande avec le numéro de la demande."
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(
        name="examiner_demande",
        description="Ouvrir une proposition de carte et afficher les boutons du staff",
    )
    @app_commands.describe(demande="Numéro de la proposition")
    async def examine_submission(
        self,
        interaction: discord.Interaction,
        demande: app_commands.Range[int, 1],
    ) -> None:
        if not await self._require_staff(interaction):
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        submission = await self.bot.card_submission_repository.get(int(demande))
        if submission is None:
            await interaction.followup.send(
                embed=error_embed(
                    "Demande introuvable",
                    "Aucune proposition ne porte ce numéro.",
                ),
                ephemeral=True,
            )
            return
        await self._send_submission_review(interaction, submission)

    @app_commands.command(
        name="synchroniser_cartes",
        description="Synchroniser toutes les cartes depuis YGOPRODeck",
    )
    async def synchronize_cards(self, interaction: discord.Interaction) -> None:
        if not await self._require_staff(interaction):
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            count = await self.bot.card_catalog_service.synchronize()
        except Exception as error:
            LOGGER.exception("Échec de la synchronisation complète")
            await interaction.followup.send(
                embed=error_embed("Synchronisation impossible", str(error)),
                ephemeral=True,
            )
            return
        await interaction.followup.send(
            embed=success_embed(
                "Catalogue synchronisé",
                f"**{count}** cartes ont été ajoutées, classées ou mises à jour.",
            ),
            ephemeral=True,
        )

    @app_commands.command(
        name="decouvrir_aleatoire",
        description="Découvrir et enregistrer immédiatement une carte aléatoire",
    )
    async def discover_random(self, interaction: discord.Interaction) -> None:
        if not await self._require_staff(interaction):
            return
        await interaction.response.defer(ephemeral=True, thinking=True)
        try:
            card = await self.bot.card_catalog_service.discover_random()
        except Exception:
            LOGGER.exception("Échec de la découverte aléatoire")
            await interaction.followup.send(
                embed=error_embed(
                    "Découverte impossible",
                    "La base externe n'a pas répondu correctement.",
                ),
                ephemeral=True,
            )
            return

        embed = card_embed(card)
        embed.title = f"🎲 {card.display_name}"
        embed.set_footer(
            text=(
                f"Carte découverte et enregistrée • ID YGOPRODeck : "
                f"{card.ygoprodeck_id}"
            )
        )
        await interaction.followup.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CardAdminCog(bot))
