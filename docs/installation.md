# Installation et premier déploiement

[Documentation](README.md)

## Prérequis

### Sur le PC

- Linux x86-64, [mise](https://mise.jdx.dev/) 2026.10.9 au minimum, OpenSSH et GNU Make pour amorcer les commandes.
- Accès HTTPS à Proxmox et SSH à la future VM.
- Clé privée correspondant à la clé publique configurée, disponible via `ssh-agent`
  ou la variable `ANSIBLE_PRIVATE_KEY_FILE`.
- Client `psql` pour vérifier ensuite une connexion SQL ; il n'est pas fourni par mise.

`mise install --locked` installe les versions définies dans [mise.toml](../mise.toml) :
OpenTofu 1.13.2, Python 3.14.8, Ansible 14.5.0 et Make 4.4.1, ainsi que
Ruff, ansible-lint, ShellCheck, actionlint, Gitleaks et Trivy pour les contrôles.
mise installe également uv 0.13.5 pour installer Ansible et ansible-lint.
Les versions exactes et leurs sources sont dans le [suivi des versions](verification.md#versions-des-outils).
Les URL et empreintes sont fixées par `mise.lock` et les graphes Python de
`.mise/locks/`. Le mode strict est activé pour le projet ; récupérer ces fichiers
avec le dépôt avant `mise install --locked`. Le verrou couvre Linux x64.
Make utilise le backend Conda intégré à mise ; aucune installation séparée de
Conda n'est nécessaire.

Make est le point d'entrée des opérations. Le shell doit utiliser les outils
sélectionnés par mise ; consulter sa [configuration du shell](https://mise.jdx.dev/installing-mise.html#shells).
Si mise n'est pas activé, exécuter `mise exec -- make <cible>`.

### Configuration globale de mise

mise combine les configurations du projet, des répertoires parents, de
l'utilisateur et du système. Avec le verrouillage strict, des outils globaux
absents du verrou de ce dépôt peuvent provoquer des erreurs d'installation,
quelle que soit la distribution du poste. Identifier les fichiers chargés :

```sh
mise config ls
```

Pour ignorer temporairement la configuration utilisateur lors de l'installation :

```sh
MISE_IGNORED_CONFIG_PATHS="${MISE_CONFIG_DIR:-${XDG_CONFIG_HOME:-$HOME/.config}/mise}" mise install --locked
```

Adapter les chemins aux fichiers affichés par `mise config ls`, notamment si
la configuration globale est placée ailleurs ou si des outils viennent du système.
Plusieurs chemins peuvent être séparés par `:` sous Linux. Cette variable agit
uniquement sur la commande préfixée ; elle ne modifie aucun fichier global.
Conserver le verrouillage strict du projet. Voir les
[chemins ignorés de mise](https://mise.jdx.dev/configuration/settings.html#ignored_config_paths).

### Sur Proxmox et le réseau

- Proxmox VE 9 sur x86-64 prenant en charge `Sys.AccessNetwork` pour les appels
  réseau du nœud, avec un CPU compatible `x86-64-v2-AES`.
- Un stockage d'image autorisant le contenu **Import**, un stockage disque
  autorisant **Disk image** et un bridge existant. Aucun template n'est requis.
- Un ID de VM disponible et une adresse IPv4 privée libre, routable depuis le PC
  et les clients PostgreSQL.
- Un accès HTTPS sortant du nœud pour télécharger Debian, puis un accès de la VM
  aux dépôts Debian et à Docker Hub.
- Des règles réseau adaptées pour SSH et les ports SQL. Les ports Docker publiés
  doivent être filtrés au niveau Proxmox ou du réseau.
- Un token API disposant des [permissions du projet](proxmox.md).

Aucun accès SSH au nœud Proxmox n'est utilisé par le déploiement. Ansible se
connecte à la VM avec le compte cloud-init, qui doit disposer de sudo sans mot de passe.

## 1. Préparer les fichiers locaux

Depuis la racine du projet :

```sh
mise trust
mise install --locked
make setup
```

`setup` copie les exemples vers `terraform/terraform.tfvars` et `databases.yml`,
sans écraser les fichiers existants. Il leur applique les permissions `0600`.

Renseigner les deux fichiers en suivant la [référence de configuration](configuration.md).
Remplacer les marqueurs réseau, la clé SSH factice et les deux mots de passe d'exemple avant les vérifications.

## 2. Préparer l'accès Proxmox

Suivre le [guide d'accès Proxmox](proxmox.md) pour créer l'utilisateur, le token
et les permissions, puis charger `PROXMOX_VE_API_TOKEN` dans le terminal du PC.
Les valeurs des ACL doivent correspondre à celles de `terraform/terraform.tfvars`.
Pour charger ensuite le token dans le terminal Bash, utiliser simplement :

```sh
source scripts/auth.sh
```

La vérification du certificat Proxmox est activée par défaut. Installer sa CA sur
le PC ou utiliser un certificat reconnu. Le paramètre `proxmox_insecure = true`
permet explicitement d'accepter un certificat non vérifié pour cet accès.

## 3. Vérifier et examiner le plan

```sh
make check
make plan
```

`check` vérifie les fichiers et la configuration locale ; il initialise aussi
OpenTofu et peut télécharger le provider. Il exécute aussi les tests OpenTofu
avec provider simulé et les outils de lint ; aucun déploiement réel n'est testé.
Sur une copie propre destinée à la CI, les fichiers locaux ne sont pas nécessaires :
ne pas exécuter `setup` si l'on souhaite seulement contrôler le dépôt.

```sh
make security
```

Cette commande vérifie les secrets, configurations IaC et vulnérabilités des
dépendances Python, de l'image PostgreSQL et des composants Go identifiables
des outils et du provider. Elle initialise le provider verrouillé et nécessite
le réseau pour les téléchargements et bases à jour. Les rapports sont écrits
dans `.reports/`, ignoré par Git. Les alertes HIGH/CRITICAL actives bloquent le contrôle. Les [risques connus](securite.md)
détaillent les alertes restantes et les exceptions justifiées.

`plan` interroge Proxmox et affiche les changements envisagés. Vérifier le nœud,
l'ID de VM, les stockages et le réseau. Cette commande ne crée pas de VM et
refuse une image existante non suivie ; voir la [maintenance de l'image](maintenance.md#image-debian).

Si une VM du projet existe déjà et que son state a été perdu, consulter la
[maintenance du state](maintenance.md#state-local) avant de poursuivre : la VM
n'est pas réimportée automatiquement.

## 4. Déployer

```sh
make deploy
```

La commande initialise OpenTofu, prépare l'image Debian et lance `apply` avec
confirmation. Elle génère ensuite `inventory.json`, valide les instances,
attend SSH et cloud-init, installe Docker et démarre les conteneurs PostgreSQL.
Elle attend leur état de santé via Compose.

Le plan présenté par `apply` doit être relu avant confirmation, même si `plan`
a déjà été exécuté : aucun fichier de plan n'est sauvegardé par ces commandes.
Un remplacement ou une destruction de VM peut entraîner la perte des données.

Au premier accès SSH, une clé hôte inconnue est acceptée. Une clé déjà connue qui
a changé est refusée ; voir le [dépannage SSH](depannage.md#connexion-ssh-impossible).

## 5. Vérifier l'accès

```sh
make status
psql -h 192.168.1.50 -p 5432 -U app -d app -W
```

Adapter l'hôte, le port, l'utilisateur et la base à la configuration. Le mot de
passe est demandé par `psql`. La suite du travail est décrite dans le
[guide d'utilisation](utilisation.md).
