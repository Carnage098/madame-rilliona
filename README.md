# Madame Rilliona V2.9 — import staff de cartes

Cette version ajoute un circuit contrôlé pour importer une carte depuis une URL ou une image PNG, puis vérifier immédiatement son enregistrement dans PostgreSQL.

## Commandes ajoutées

### `/base ajouter_carte`

Options :

- `source` : **Site internet** ou **Image PNG** ;
- `nom` : nom français, nom anglais ou identifiant YGOPRODeck ;
- `url` : page de référence pour le mode site ;
- `image` : pièce jointe `.png` pour le mode image.

Fonctionnement :

1. le bot vérifie que l'utilisateur appartient au staff ;
2. il identifie la carte ;
3. il récupère ses données françaises et anglaises depuis YGOPRODeck ;
4. il enregistre l'effet, le classement, les statistiques, l'archétype et les images ;
5. il relit la fiche depuis PostgreSQL ;
6. il affiche un contrôle détaillé ;
7. il journalise l'import dans la table `card_imports`.

### `/base verifier_carte`

Cette commande ne consulte pas le site externe. Elle vérifie directement la base locale :

- présence dans PostgreSQL ;
- nom ;
- effet ou description ;
- classement ;
- image disponible.

## Sources URL

- Une URL YGOPRODeck peut être utilisée seule lorsqu'elle contient un nom ou un identifiant exploitable.
- Pour un autre site, renseigne également l'option `nom`. Madame Rilliona conserve l'URL comme référence mais utilise YGOPRODeck pour obtenir une fiche structurée et cohérente.
- Le bot ne télécharge pas les pages des sites tiers, ce qui évite les accès réseau non sûrs et les extracteurs fragiles.

## Images PNG

- Taille maximale par défaut : 10 Mo.
- Le fichier est contrôlé grâce à sa signature PNG et à son en-tête de dimensions.
- L'option `nom` est recommandée. Elle est requise si le fichier porte un nom générique comme `image.png`.
- Le PNG du staff est enregistré dans `CARD_IMAGE_DIRECTORY` et devient prioritaire sur l'image YGOPRODeck.

## Vérification du staff

Un membre est accepté s'il possède au moins l'un des éléments suivants :

- Administrateur ;
- Gérer le serveur ;
- Gérer les messages ;
- un rôle configuré dans `STAFF_ROLE_IDS`.

Exemple Railway :

```env
STAFF_ROLE_IDS=123456789012345678,987654321098765432
MAX_STAFF_IMAGE_BYTES=10485760
```

`STAFF_ROLE_ID` avec un seul identifiant reste également accepté.

## Base de données

La migration automatique crée :

```text
card_imports
```

Chaque tentative conserve :

- la carte concernée ;
- l'identifiant Discord de l'auteur ;
- le type de source ;
- l'URL ou le nom du fichier ;
- le résultat de l'import ;
- le résultat de la vérification ;
- la date.

## Railway

Place les fichiers directement à la racine du dépôt :

```text
bot.py
config.py
database_manager.py
requirements.txt
railway.toml
cogs/
models/
repositories/
services/
utils/
```

Commande de démarrage :

```text
python bot.py
```

Pour conserver les PNG du staff après les redéploiements, monte un volume Railway sur le chemin défini par `CARD_IMAGE_DIRECTORY`, par défaut `/app/data/card_images`.


## Découverte rapide V3.1

La tâche autonome effectue une tentative toutes les 60 secondes. Avant toute insertion, le bot vérifie l’identifiant dans PostgreSQL. Une carte déjà connue est ignorée et un autre tirage est tenté, jusqu’à la limite configurée.

Variables Railway :

```env
RANDOM_DISCOVERY_ENABLED=true
RANDOM_DISCOVERY_INTERVAL_SECONDS=60
RANDOM_DISCOVERY_MAX_ATTEMPTS=8
RANDOM_DISCOVERY_INITIAL_DELAY_SECONDS=30
```

L’ancienne variable `RANDOM_DISCOVERY_INTERVAL_MINUTES` n’est plus utilisée.
