# Madame Rilliona V2.6 — recherche de cartes corrigée

Cette version corrige la commande `/carte rechercher` lorsque le catalogue local
est vide, incomplet ou que le nom contient des accents, tirets ou apostrophes.

## Fonctionnement de la recherche

1. Recherche par identifiant YGOPRODeck dans PostgreSQL.
2. Recherche classique dans les noms français et anglais locaux.
3. Recherche normalisée locale, tolérante aux accents et à la ponctuation.
4. Recherche automatique dans l'API YGOPRODeck en français.
5. Récupération des données anglaises par identifiant.
6. Enregistrement automatique de la carte dans PostgreSQL.

Ainsi, la carte suivante fonctionne même avant une synchronisation complète :

```text
Dragon Blanc aux Yeux Bleus
```

## Structure

```text
bot.py
config.py
database_manager.py
requirements.txt
railway.toml
startup_check.py
cogs/
models/
repositories/
services/
utils/
```

## Installation GitHub/Railway

1. Remplacer intégralement l'ancienne version par le contenu de cette archive.
2. Ne pas conserver un ancien dossier `database/`, un ancien `database.py`,
   `start.py` ou `flat_import_compat.py`.
3. Laisser le Root Directory Railway vide lorsque `bot.py` est à la racine.
4. Utiliser `python bot.py` comme commande de démarrage.
5. Conserver `DISCORD_TOKEN`, `DATABASE_URL`, `GUILD_ID`,
   `CARD_IMAGE_DIRECTORY` et `LOG_LEVEL`.

## Commandes utiles

```text
/carte rechercher carte:Dragon Blanc aux Yeux Bleus
/base statut
/base synchroniser_cartes
```

`/base synchroniser_cartes` reste recommandé pour remplir tout le catalogue,
notamment pour l'autocomplétion et `/carte archetype`, mais il n'est plus
obligatoire pour rechercher une carte précise.
