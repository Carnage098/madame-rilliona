# Madame Rilliona V3.0 — validation staff et doublons

Cette version ajoute un vrai circuit de proposition publique : une carte proposée par un membre n'entre pas dans le catalogue avant la décision du staff.

## Commandes

### Membres

```text
/carte proposer
```

Sources acceptées :

- une URL HTTPS ;
- une image PNG ;
- un nom français, anglais ou un identifiant pour aider à reconnaître la carte.

Le bot prépare la fiche depuis YGOPRODeck, enregistre la demande dans `card_submissions`, vérifie les doublons, puis l'envoie dans le salon de validation.

### Staff

```text
/base demandes
/base examiner_demande
/base ajouter_carte
/base verifier_carte
```

`/base ajouter_carte` reste un ajout immédiat réservé au staff. Pour le circuit avec validation, les membres utilisent `/carte proposer`.

## Boutons de validation

- **Valider** : ajoute une nouvelle carte si aucun doublon bloquant n'existe.
- **Mettre à jour** : remplace les données d'une fiche ayant exactement le même identifiant YGOPRODeck.
- **À corriger** : ferme la demande et demande au membre d'en envoyer une nouvelle version corrigée.
- **Refuser** : ferme la demande sans ajouter la carte.

Les boutons sont persistants : ils sont restaurés après un redémarrage du bot.

## Détection des doublons

Madame Rilliona compare :

- l'identifiant YGOPRODeck ;
- le nom français normalisé ;
- le nom anglais normalisé ;
- les noms très ressemblants.

Une deuxième proposition active portant sur le même identifiant est refusée automatiquement.

## Variables Railway

```env
DISCORD_TOKEN=...
DATABASE_URL=${{Postgres.DATABASE_URL}}
GUILD_ID=...
STAFF_ROLE_IDS=123456789012345678
CARD_REVIEW_CHANNEL_ID=123456789012345678
CARD_IMAGE_DIRECTORY=/app/data/card_images
MAX_STAFF_IMAGE_BYTES=10485760
LOG_LEVEL=INFO
```

`CARD_REVIEW_CHANNEL_ID` est recommandé. Sans cette variable, les demandes restent accessibles avec `/base demandes` et `/base examiner_demande`.

## Permissions dans le salon de validation

Le bot doit pouvoir :

- voir le salon ;
- envoyer des messages ;
- intégrer des liens ;
- joindre des fichiers ;
- voir les anciens messages.

## Railway

```text
Root Directory : vide
Start Command : python bot.py
```

Un volume persistant monté sur `/app/data` est recommandé pour conserver les PNG proposés et validés après les redéploiements.
