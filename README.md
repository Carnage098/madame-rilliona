# Madame Rilliona V2.7 — catalogue autonome

Madame Rilliona construit maintenant progressivement sa propre bibliothèque Yu-Gi-Oh!.

## Enregistrement automatique

- `/carte rechercher` cherche localement, puis interroge YGOPRODeck si nécessaire.
- Toute carte trouvée est enregistrée dans PostgreSQL.
- Les noms et effets français et anglais sont conservés quand ils existent.
- Les images sont téléchargées une seule fois au moment où elles sont affichées.

## Classement des cartes

Chaque carte est classée avec :

- catégorie : Monstre, Magie, Piège, Compétence, Jeton ou Autre ;
- emplacement : Main Deck, Extra Deck, Zone Magie/Piège ou hors Deck principal ;
- type précis et `frameType` ;
- race/type, attribut, Niveau, Rang, Lien, ATK, DEF et Échelle Pendule ;
- typeline et marqueurs Lien ;
- archétype ;
- statut des banlists TCG, OCG et GOAT lorsqu'il est fourni ;
- source de l'import : recherche, archétype, découverte aléatoire ou catalogue complet.

## Archétypes

`/archetype ajouter` :

1. reconnaît le nom canonique de l'archétype ;
2. accepte également un nom français pouvant être déduit des cartes françaises ;
3. télécharge toutes les cartes anglaises et françaises de l'archétype ;
4. les classe et les enregistre ;
5. crée ensuite la fiche locale de l'archétype.

Commandes supplémentaires :

- `/archetype synchroniser` met à jour toutes les cartes d'un archétype ;
- `/carte archetype` importe automatiquement l'archétype si aucune carte locale n'existe ;
- `/base decouvrir_aleatoire` enregistre immédiatement une carte aléatoire ;
- `/base statut` affiche le nombre de cartes et leur répartition par catégorie.

## Découverte aléatoire en arrière-plan

Par défaut, le bot enregistre une carte aléatoire environ toutes les six heures, avec une légère variation aléatoire de l'intervalle.

Variables Railway :

```env
RANDOM_DISCOVERY_ENABLED=true
RANDOM_DISCOVERY_INTERVAL_MINUTES=360
RANDOM_DISCOVERY_INITIAL_DELAY_SECONDS=300
```

La valeur minimale de l'intervalle est de 60 minutes. Mets `RANDOM_DISCOVERY_ENABLED=false` pour désactiver cette fonction.

## Installation Railway

Place directement à la racine du dépôt :

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

La migration PostgreSQL est automatique au démarrage. Les anciennes cartes restent présentes et reçoivent les nouveaux champs lorsqu'elles sont retrouvées ou resynchronisées.
