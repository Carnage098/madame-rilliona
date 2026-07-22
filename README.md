# Madame Rilliona V2.3 — correctif complet Railway

Cette version restaure la structure Python normale du projet. Elle ne dépend plus de
`start.py` ni de `flat_import_compat.py`.

## Structure

```text
bot.py
config.py
database.py
requirements.txt
railway.toml
cogs/
models/
repositories/
services/
utils/
```

## Installation sur GitHub/Railway

1. Supprimer les anciens `start.py` et `flat_import_compat.py`.
2. Copier **tout** le contenu de ce dossier à la racine du dépôt.
3. Vérifier que `bot.py` et le dossier `repositories` sont au même niveau.
4. Laisser le Root Directory Railway vide.
5. Utiliser `python bot.py` comme commande de démarrage.
6. Conserver les variables `DISCORD_TOKEN`, `DATABASE_URL`, `GUILD_ID` et
   `CARD_IMAGE_DIRECTORY`.

Les tables PostgreSQL sont créées automatiquement au démarrage.


## Correctif V2.4 — conflit `database`

La connexion PostgreSQL est maintenant définie dans `database_manager.py`. `bot.py` utilise `from database_manager import Database`, ce qui évite tout conflit avec un éventuel ancien dossier `database/` présent dans le dépôt.

## Correctif V2.5

Cette archive est une version complète. Elle ne doit pas être copiée par-dessus
un dépôt contenant des fichiers de versions précédentes. Consulte
`INSTALLATION_PROPRE.txt` et remplace intégralement l'ancien code.
