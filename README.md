# Madame Rilliona V3.2 — encyclopédie stratégique

Cette version conserve la validation du staff, la détection des doublons et la découverte d'une carte toutes les 60 secondes. Elle ajoute une couche stratégique au catalogue PostgreSQL.

## Nouveautés principales

### Rôles stratégiques des cartes

Le staff peut attribuer plusieurs fonctions à une même carte :

- Starter ;
- Extender ;
- Brick ;
- Handtrap ;
- Board Breaker ;
- Interaction ;
- Follow-up ;
- Boss Monster ;
- Carte de Side ;
- Pièce de combo.

Commandes :

```text
/carte definir_role
/carte retirer_role
```

Une note facultative peut expliquer pourquoi la carte possède ce rôle. Les rôles apparaissent ensuite dans `/carte rechercher`, `/carte filtrer` et les fiches d'archétypes.

### Alias et surnoms

Le staff peut associer des abréviations, surnoms ou traductions supplémentaires à une carte :

```text
/carte ajouter_alias
/carte retirer_alias
```

Exemples :

```text
BEWD
Dragon Blanc
Blue Eyes
```

Les alias sont normalisés pour accepter les différences de ponctuation, d'espaces et d'accents. Un alias ne peut pas être associé à deux cartes ni reprendre le nom officiel d'une autre carte.

### Recherche avancée

```text
/carte filtrer
```

Filtres disponibles :

- archétype ;
- catégorie ;
- emplacement dans le Deck ;
- attribut ;
- type de monstre ;
- texte contenu dans l'effet ;
- rôle stratégique ;
- ATK minimale ou maximale ;
- Niveau ;
- Rang ;
- valeur Lien ;
- nombre maximal de résultats.

La recherche utilise uniquement les données enregistrées dans PostgreSQL.

### Fiches d'archétypes intelligentes

```text
/archetype consulter
/archetype strategie
```

La fiche présente maintenant :

- la répartition Monstres/Magies/Pièges ;
- les cartes du Main Deck et de l'Extra Deck ;
- le nombre de Starters, Extenders, Boss Monsters et autres rôles ;
- les cartes correspondant à un rôle sélectionné.

### Diagnostic de la base

```text
/base diagnostic
```

Cette commande réservée au staff contrôle :

- les cartes sans effet français ;
- les cartes sans image distante ;
- les cartes sans classement ;
- les cartes sans archétype ;
- les cartes sans rôle stratégique ;
- les alias et rôles enregistrés ;
- les propositions en attente ;
- les noms dupliqués potentiels ;
- les archétypes vides ;
- les combos sans étape ;
- la dernière découverte aléatoire.

## Nouvelles tables PostgreSQL

La migration automatique crée :

```text
card_aliases
card_roles
```

Aucune carte, aucun archétype, aucun combo et aucune proposition existante ne sont supprimés.

## Découverte aléatoire

Configuration recommandée :

```env
RANDOM_DISCOVERY_ENABLED=true
RANDOM_DISCOVERY_INTERVAL_SECONDS=60
RANDOM_DISCOVERY_MAX_ATTEMPTS=8
RANDOM_DISCOVERY_INITIAL_DELAY_SECONDS=30
```

Chaque minute, Madame Rilliona vérifie l'identifiant officiel avant insertion. Une carte déjà présente est ignorée et un autre tirage est tenté.

## Variables Railway

```env
DISCORD_TOKEN=
DATABASE_URL=
GUILD_ID=
CARD_IMAGE_DIRECTORY=/app/data/card_images
LOG_LEVEL=INFO
RANDOM_DISCOVERY_ENABLED=true
RANDOM_DISCOVERY_INTERVAL_SECONDS=60
RANDOM_DISCOVERY_MAX_ATTEMPTS=8
RANDOM_DISCOVERY_INITIAL_DELAY_SECONDS=30
STAFF_ROLE_IDS=
CARD_REVIEW_CHANNEL_ID=
MAX_STAFF_IMAGE_BYTES=10485760
```

## Déploiement Railway

Place tous les fichiers directement à la racine du dépôt :

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
views/
```

Configuration :

```text
Root Directory : vide
Start Command : python bot.py
```

Pour conserver les images PNG après un redéploiement, monte un volume sur `/app/data/card_images` ou sur le chemin défini dans `CARD_IMAGE_DIRECTORY`.
