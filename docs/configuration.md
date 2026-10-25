# Configuration

[Documentation](README.md) · [Installation](installation.md)

Deux fichiers locaux sont à renseigner après `make setup`. Ils sont ignorés
par Git et doivent conserver des permissions `0600`.

| Fichier | Usage | Modèle |
| --- | --- | --- |
| `terraform/terraform.tfvars` | Accès Proxmox, VM, réseau et ressources | [terraform.tfvars.example](../terraform/terraform.tfvars.example) |
| `databases.yml` | Instances PostgreSQL | [databases.yml.example](../databases.yml.example) |

Le token API se charge dans `PROXMOX_VE_API_TOKEN`, selon le [guide Proxmox](proxmox.md).
Un fichier `.env` n'est pas chargé automatiquement.

## Organisation des fichiers OpenTofu

| Fichier | Rôle |
| --- | --- |
| [versions.tf](../terraform/versions.tf) | Versions requises d'OpenTofu et du provider Proxmox |
| [providers.tf](../terraform/providers.tf) | Configuration de l'accès API Proxmox |
| [image.tf](../terraform/image.tf) | Image Debian utilisée pour créer le disque de la VM |
| [main.tf](../terraform/main.tf) | VM, ressources, réseau et initialisation cloud-init |
| [variables.tf](../terraform/variables.tf) | Entrées de configuration, valeurs par défaut et validations |
| [outputs.tf](../terraform/outputs.tf) | Inventaire transmis à Ansible |

OpenTofu charge tous les fichiers `.tf` du dossier ensemble. Leur séparation
sert à la lecture ; elle ne crée pas de modules ni d'étapes de déploiement distinctes.

## Infrastructure

La référence des variables est [variables.tf](../terraform/variables.tf).
Les valeurs ci-dessous sont des exemples ; les valeurs par défaut sont indiquées
séparément lorsqu'elles existent.

| Variable | Rôle et contraintes | Exemple / défaut |
| --- | --- | --- |
| `proxmox_endpoint` | URL de l'API, commençant par `https://` | `https://pve.example.net:8006/` |
| `proxmox_insecure` | Désactive la vérification du certificat Proxmox | Défaut : `false` |
| `node_name` | Nom du nœud Proxmox | `pve` |
| `image_storage` | Stockage autorisant le contenu Import | `local` |
| `disk_storage` | Stockage des disques VM et cloud-init | `local-lvm` |
| `bridge` | Bridge réseau existant | Défaut : `vmbr0` |
| `vm_id` | Entier entre 100 et 999999999, disponible pour une nouvelle VM | `200` |
| `vm_name` | Nom de la VM | Défaut : `iac-postgres` |
| `ipv4_address` | IPv4 privée RFC1918 avec préfixe CIDR | `192.168.1.50/24` |
| `ipv4_gateway` | Passerelle IPv4 | `192.168.1.1` |
| `dns_servers` | Liste non vide d'adresses IPv4 | `["192.168.1.1"]` |
| `ssh_user` | Compte Linux non root ; lettres minuscules, chiffres, `_`, `-`, début par lettre ou `_`, 32 caractères maximum | Défaut : `debian` |
| `ssh_public_key` | Contenu d'une clé publique OpenSSH, jamais la clé privée | Clé Ed25519, RSA ou ECDSA |
| `cpu_cores` | Entier positif | Défaut : `2` |
| `memory_mb` | Entier d'au moins 1024 Mio | Défaut : `4096` |
| `disk_gb` | Entier d'au moins 8 Gio | Défaut : `40` |

Les images Debian et PostgreSQL sont épinglées dans [dependencies.json](../dependencies.json),
avec leurs empreintes ; le type de CPU reste défini dans le code. Ces paramètres
ne sont pas des variables de configuration locale. Les permissions du token doivent couvrir
le stockage, le bridge et l'ID de VM choisis.

### Adresses à personnaliser

Les marqueurs `REMPLACER_IPV4_VM/PREFIXE`, `REMPLACER_PASSERELLE` et
`REMPLACER_DNS` du fichier d'exemple sont volontairement invalides. Renseigner
une IPv4 privée libre avec son préfixe CIDR, la passerelle et les DNS adaptés au
réseau. Le stockage disque peut par exemple s'appeler `local-lvm` ou `local-zfs` ;
utiliser le nom du stockage réellement configuré sur Proxmox.

La validation refuse l'IP de VM lorsqu'elle est identique à l'IPv4 écrite dans
`proxmox_endpoint`. Pour une URL utilisant un nom DNS, elle ne résout pas ce nom :
vérifier manuellement que la VM n'utilise aucune adresse de Proxmox ou d'une autre
machine. Ce contrôle ne recherche pas les adresses déjà utilisées sur le réseau.

## Instances PostgreSQL

`databases.yml` contient une liste `databases`. Chaque entrée crée une instance
PostgreSQL distincte, avec sa base initiale et son utilisateur.

```yaml
databases:
  - id: app
    name: app
    user: app
    password: "CHANGE_ME_USE_A_RANDOM_PASSWORD"
    port: 5432

  - id: analytics
    name: analytics
    user: analytics
    password: "CHANGE_ME_USE_ANOTHER_RANDOM_PASSWORD"
    port: 5433
```

Cet exemple déclare deux instances sur la même VM : `app` sur le port 5432 et
`analytics` sur le port 5433. Les mots de passe sont volontairement refusés.
Les remplacer chacun par un secret aléatoire distinct avant de lancer `check`
ou `configure`. Retirer la deuxième entrée si une seule instance est souhaitée.

| Champ | Contraintes |
| --- | --- |
| `id` | Identifiant unique et stable, 1 à 31 caractères |
| `name` | Nom de la base initiale, 1 à 63 caractères |
| `user` | Utilisateur initial, 1 à 63 caractères ; préfixe `pg_` interdit |
| `password` | Chaîne d'au moins 20 caractères, sans retour à la ligne ni caractère NUL |
| `port` | Entier YAML sans guillemets, unique dans la liste, entre 1024 et 65535 |

`id`, `name` et `user` commencent par une lettre minuscule et contiennent seulement
`a-z`, `0-9` et `_`. Le validateur refuse aussi les mots de passe contenant des
marqueurs d'exemple, notamment `CHANGE_ME`, `remplacer`, `example`, `exemple`,
`password` ou `mot de passe`, sans distinction de casse.

Les caractères `$`, guillemets, `:` et `\` sont acceptés dans le secret, à condition
de respecter la syntaxe YAML. Le secret est écrit dans un fichier distinct du
Compose ; les tâches qui le manipulent masquent leurs sorties.

Une liste vide (`databases: []`) est acceptée. Elle ne supprime aucune instance
existante. Les erreurs indiquent le champ et l'index à partir de zéro, par
exemple `databases[0] : password…`, sans afficher la valeur du secret.

## Effet des changements

| Modification | Comportement |
| --- | --- |
| Ajouter une entrée avec un nouvel `id` | Crée une autre instance lors de `configure` |
| Changer `id` | Utilise un autre projet et un autre volume ; les anciennes données restent dans l'ancien volume |
| Changer `port` | Modifie le port publié lors de `configure` ; vérifier qu'il est libre sur la VM |
| Changer `name`, `user` ou `password` | Modifie la configuration d'initialisation ; ne modifie pas une base déjà initialisée |
| Retirer une entrée | Laisse le conteneur, le projet et le volume existants en place |
| Modifier l'infrastructure | Nécessite `plan`, puis `apply` ou `deploy` ; examiner tout remplacement de VM |

Le changement d'un mot de passe existant nécessite une rotation SQL séparée, puis
la synchronisation du YAML. L'utilisateur initial est un superutilisateur de son
instance PostgreSQL.
