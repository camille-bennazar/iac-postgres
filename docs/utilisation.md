# Utilisation

[Documentation](README.md) · [Configuration](configuration.md)

Toutes les commandes se lancent depuis la racine du projet avec Make.
mise fournit les versions des outils ; si son activation dans le shell n'est pas
configurée, utiliser `mise exec -- make <cible>`.

## Choisir une commande

| Commande | Effet |
| --- | --- |
| `make setup` | Crée les configurations locales manquantes depuis les exemples et protège leurs permissions |
| `make check` | Vérifie OpenTofu, les tests simulés, Ansible, Compose, les tests Python et le lint |
| `make test` | Exécute les scénarios Python avec leur bilan lisible |
| `make lint` | Vérifie Python, Ansible, Bash, les workflows et les liens locaux |
| `make security` | Vérifie les secrets, configurations et vulnérabilités HIGH/CRITICAL |
| `make clear` | Archive les fichiers générés, y compris le state, dans `./tmp/` |
| `make restore` | Liste les archives disponibles |
| `make clear-tmp` | Supprime les archives, en protégeant les states non restaurés |
| `make plan` | Initialise OpenTofu, prépare l'image et affiche les changements d'infrastructure |
| `make apply` | Initialise OpenTofu, prépare l'image et applique l'infrastructure après confirmation |
| `make configure` | Génère l'inventaire depuis le state puis applique Ansible sur la VM |
| `make deploy` | Exécute `apply`, puis `configure` |
| `make status` | Génère l'inventaire puis affiche les conteneurs PostgreSQL, leur état et leurs ports |

Charger le token dans le terminal Bash avec `source scripts/auth.sh` avant les
opérations Proxmox. `make auth` affiche cette instruction ; il n'exporte pas de variable.

Les commandes Make prennent un verrou de projet et refusent un deuxième appel
concurrent. Les commandes d'infrastructure refusent un state encore archivé ;
voir le [nettoyage et la restauration](maintenance.md#nettoyage-et-restauration).

`configure` peut installer ou réappliquer Docker et les projets Compose ; il ne
modifie pas les ressources Proxmox. `apply` ne lance pas Ansible.

`plan`, `apply` et `deploy` nécessitent le token API chargé dans le terminal.
La préparation de l'image vérifie son suivi et bloque les fichiers existants
non suivis ; voir la [réutilisation de l'image Debian](maintenance.md#image-debian).

`configure` et `status` ont besoin des sorties d'un state existant et d'un accès
SSH à la VM. `status` liste aussi les conteneurs des entrées retirées du YAML.
Son filtre porte sur le service Compose `postgres` ; d'autres projets présents
sur la même VM avec ce nom de service peuvent aussi apparaître.

### Cibles Make complémentaires

Ces cibles complètent les opérations courantes :

| Commande | Effet |
| --- | --- |
| `make help` | Affiche les noms des commandes courantes |
| `make init` | Initialise OpenTofu dans `terraform/` |
| `make check-local` | Vérifie Ansible, la configuration locale, le rendu Compose et les tests Python |
| `make prepare-image` | Initialise OpenTofu et contrôle le suivi de l'image ; refuse une adoption automatique |
| `make inventory` | Écrit `inventory.json` depuis la sortie OpenTofu `ansible_inventory` |

Aucune de ces commandes ne gère automatiquement la suppression des anciennes
instances ou la rotation des mots de passe existants.

## Ajouter une instance

1. Ajouter une entrée à `databases.yml` en conservant les instances souhaitées.
2. Choisir un `id` et un port uniques ; vérifier aussi les anciens conteneurs avec `status`.
3. Vérifier la configuration, puis appliquer Ansible :

```sh
make check-local
make configure
make status
```

Le [guide de configuration](configuration.md) détaille les champs et les effets
possibles d'une modification.

## Se connecter

Depuis un poste disposant de `psql` et d'un accès réseau à la VM :

```sh
psql -h 192.168.1.50 -p 5432 -U app -d app -W
```

Remplacer l'adresse par celle de la VM sans le préfixe CIDR, puis reprendre
`port`, `user` et `name` dans l'entrée concernée. `-W` demande le mot de passe
sans l'inscrire dans la commande.

## Réappliquer une configuration

Après une modification de `databases.yml`, lancer `make configure`.
Les volumes existants sont conservés lors d'une recréation des conteneurs.

Après une modification de `terraform/terraform.tfvars`, examiner `make plan`
puis lancer `make deploy` pour appliquer l'infrastructure et Ansible.
`make apply` convient si seule l'infrastructure doit être appliquée.

Retirer une entrée YAML laisse l'instance existante en place. Sa suppression
reste manuelle. Ne pas réutiliser son port tant que son conteneur tourne.
