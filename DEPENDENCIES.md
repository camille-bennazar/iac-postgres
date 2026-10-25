# Dépendances

Inventaire des dépendances déclarées dans le dépôt au **22 octobre 2026**.
Les versions ci-dessous décrivent la configuration du projet, pas un relevé
des logiciels effectivement présents sur une VM. Les fichiers de référence
restent [mise.toml](mise.toml), [mise.lock](mise.lock),
[dependencies.json](dependencies.json), [versions.tf](terraform/versions.tf), le
[verrou du provider](terraform/.terraform.lock.hcl), les
[workflows](.github/workflows/ci.yml) et les playbooks Ansible.

## Poste de travail et outils de contrôle

| Composant | Version déclarée | Origine / installation | Utilisation |
| --- | --- | --- | --- |
| Linux x86-64 | Distribution non épinglée | Système du poste | Plateforme verrouillée `linux-x64` ; `fcntl`, permissions Unix et pseudo-terminaux dans les scripts/tests |
| Bash | Non épinglée | Système du poste | Makefile, chargement interactif du token et tests d'authentification |
| OpenSSH client | Non épinglée | Système du poste | Connexion Ansible, clé privée ou agent SSH |
| Autorités de certification | Non épinglées | Système du poste | HTTPS vers Proxmox et les sources de téléchargement |
| mise | Minimum 2026.10.9 sur le poste ; 2026.10.15 en CI | Gestionnaire d'outils, installé au préalable | Binaire CI vérifié par SHA-256 déclaré dans `dependencies.json` |
| GNU Make | 4.4.1 | Backend mise `conda:make`, canal conda-forge | Orchestration des commandes ; Make système nécessaire à l'amorçage selon l'installation |
| OpenTofu | 1.13.2 | mise | Provisionnement ; contrainte HCL `>= 1.10.7, < 2.0.0` |
| Provider `bpg/proxmox` | 0.118.0 | Registre OpenTofu | API Proxmox ; version et empreintes dans `.terraform.lock.hcl` |
| Python | 3.14.8 | mise | Scripts locaux et outils Python |
| uv | 0.13.5 | mise | Backend PyPI, avec `settings.pypi.uvx = true` |
| Ansible | 14.5.0 | mise, installation Python via uv | Playbooks, modules `ansible.builtin`, filtres de rendu |
| Ruff | 0.17.1 | mise | Analyse statique Python |
| ansible-lint | 26.10.1 | Backend mise `pypi:ansible-lint` isolé | Analyse des playbooks, profil `production`, mode hors ligne |
| ShellCheck | 0.11.0 | mise | Analyse Bash |
| actionlint | 1.7.12 | mise | Analyse des workflows GitHub |
| Gitleaks | 8.30.1 | mise | Recherche de secrets dans les fichiers, l'index et l'historique Git |
| Trivy | 0.76.1 | mise | Configurations et vulnérabilités Python, image PostgreSQL, provider et outils Go `HIGH` et `CRITICAL` |
| Git | Non épinglée | Système du poste / runner | Historique et index utilisés par les scans ; tests de sécurité |
| Docker et Compose locaux | Non épinglés, facultatifs | Installation du poste | Validation supplémentaire du rendu via `docker compose config` |
| Client PostgreSQL `psql` | Non épinglée, facultative pour l'automatisation | Installation du poste | Vérification manuelle des connexions SQL |

Les scripts Python du dépôt utilisent exclusivement la bibliothèque standard :
`contextlib`, `errno`, `fcntl`, `hashlib`, `importlib.util`, `io`, `ipaddress`, `json`, `os`,
`pathlib`, `pty`, `re`, `select`, `shlex`, `shutil`, `ssl`, `subprocess`, `sys`, `tempfile`,
`time`, `tomllib`, `unittest` (dont `unittest.mock`), `zipfile` et `urllib` (`error`, `parse`, `request`).
Il n'y a pas de `requirements.txt` applicatif ni de dépendance pytest.

Les versions, backends, URL et empreintes des outils sont dans `mise.lock`.
Les dépendances Conda de Make y sont également verrouillées avec leurs builds,
URL et SHA-256. Les dépendances Python d'Ansible et d'ansible-lint sont résolues
dans deux graphes versionnés sous `.mise/locks/`, avec versions, marqueurs Python
et plateforme et empreintes des wheels. Leur contrainte `requires-python` est
`==3.14.*`, alignée sur le Python du projet : les branches destinées aux autres
versions de Python ne font pas partie de ces graphes. Mise installe ces graphes via uv sans
nouvelle résolution et vérifie leurs empreintes. L'installation verrouillée
ne construit pas de distributions source.

Le mode strict est défini par `tool_config.locked = true` pour le projet et
explicitement par `--locked` en CI. Il ne modifie pas les outils globaux du poste.
Les vérifications de provenance (attestations GitHub ou Cosign lorsqu'elles sont
disponibles) sont enregistrées selon le backend ; une empreinte seule ne prouve
pas l'identité d'un éditeur ni l'absence de vulnérabilités.

Les collections livrées avec Ansible font partie de son wheel épinglé. Les playbooks
n'utilisent aucune collection externe à `ansible.builtin` et n'appellent pas de
module `community.docker` : Compose est invoqué par sa CLI. Le scan Python porte
sur les paquets du graphe, pas sur un audit distinct de chaque collection embarquée.

## Proxmox et système invité

| Composant | Version / référence | Installation ou responsabilité |
| --- | --- | --- |
| Proxmox VE | Cible documentée : 9, correctif non épinglé | Préexistant, non installé par le projet |
| QEMU/KVM et services Proxmox | Versions de l'hôte | Gérés par Proxmox ; CPU requis `x86-64-v2-AES` |
| Stockages et bridge | Noms configurables | Préexistants ; image `import`, disque VM et cloud-init, bridge réseau |
| Debian invité | 13, build `20261021-2638` | URL datée et SHA-512 dans `dependencies.json`, vérifiés par Proxmox au téléchargement |
| cloud-init | Version incluse dans l'image | Configuration réseau et compte SSH ; attendu par Ansible |
| Python invité | `/usr/bin/python3`, version Debian | Nécessaire aux modules Ansible ; doit être présent dans l'image |
| Serveur SSH et sudo | Versions Debian | Accès du compte cloud-init ; sudo sans mot de passe requis |
| systemd, APT et certificats | Versions Debian | Gestion du service Docker, paquets et téléchargements |
| `docker.io` | Version disponible dans les dépôts configurés | Installé par Ansible, `state: present` |
| `docker-cli` | Version disponible dans les dépôts configurés | Installé par Ansible, commande `docker` |
| `docker-compose` | Version disponible dans les dépôts configurés | Installé par Ansible ; plugin Compose v2 ou supérieur, avec `up --wait` et `--wait-timeout` vérifiés par Ansible |

Le projet n'ajoute pas le dépôt Docker CE. Les dépendances APT de ces paquets
(runtime de conteneurs, réseau et bibliothèques système) sont résolues par Debian,
sans snapshot ni fichier de verrou dans ce dépôt. Les signatures APT restent
vérifiées par Debian ; aucun gel de paquets ne bloque les correctifs système.
`state: present` ne définit pas une politique
de mise à niveau des paquets déjà installés. Le guest agent QEMU est désactivé
et n'est pas installé par les playbooks.

## PostgreSQL et stockage

| Composant | Référence | Détail |
| --- | --- | --- |
| Image officielle PostgreSQL | `postgres:17.11-alpine3.24` avec digest SHA-256 | Référence complète dans `dependencies.json`, consommée par Ansible et le scanner |
| `pg_isready` | Fourni par l'image | Healthcheck du conteneur, sans preuve de connexion applicative complète |
| Bibliothèques et OS du conteneur | Fixés par le digest | Alpine Linux 3.24 avec musl, distinct de Debian 13 dans la VM |
| Volume Docker | `pg_<id>_data` | Données montées dans `/var/lib/postgresql/data`, sur le disque de la VM |
| Réseau Docker | `pg_<id>_network` | Un réseau par projet Compose ; port publié sur l'IP de la VM |
| Secret Compose | Fichier `postgres_password` | Monté sous `/run/secrets/postgres_password`, sans coffre externe |

Le digest empêche un tag modifié en amont de changer silencieusement l'image
choisie. Les correctifs nécessitent une actualisation volontaire de cette
référence après scan et sauvegarde. Aucun outil de sauvegarde, de réplication,
de supervision ou de gestion des certificats PostgreSQL n'est installé par le projet.

## CI et mises à jour

Les deux workflows utilisent un runner `ubuntu-24.04` dont l'image et les outils
préinstallés évoluent. Les références complètes sont dans
[ci.yml](.github/workflows/ci.yml) et [security.yml](.github/workflows/security.yml).

| Action | Version commentée | SHA épinglé |
| --- | --- | --- |
| `actions/checkout` | v7.0.1 | `3d3c42e5aac5ba805825da76410c181273ba90b1` |
| `jdx/mise-action` | v5.2.1 | `fc42bcc7ddbf51124c30f95a877a0c5168a3bfde` |
| `actions/upload-artifact` | v7.0.2 | `cf430e030ddbb5b0abf93d22962f4752f3646cd9` |
| `actions/cache/restore`, `actions/cache/save` | v6.1.0 | `55cc8345863c7cc4c66a329aec7e433d2d1c52a9` |

Dependabot surveille chaque semaine les actions GitHub uniquement. Les données
de contrôle de Trivy sont téléchargées par l'outil ; elles ne sont pas épinglées
dans le dépôt. Les règles Gitleaks par défaut viennent de la version installée,
complétées par les fichiers TOML du projet. La CI n'a pas de secret Proxmox.
Le bootstrap mise est vérifié par SHA-256 et une politique statique contrôle les
verrous avant l'installation. Les scans incluent les graphes Python et le digest
PostgreSQL pour Linux amd64. Les dépendances Go identifiables des binaires
OpenTofu, actionlint, Gitleaks, Trivy et du provider sélectionné sont aussi
analysées ; les anciennes versions présentes dans un cache ne sont pas les cibles.

## Services externes et réseau

| Service | Consommateur | Besoin |
| --- | --- | --- |
| Sources des backends mise, GitHub Releases, index Python et conda-forge | Poste et CI | Installer les outils ; endpoints précis selon les backends |
| Registre OpenTofu et distributions du provider | Poste et CI | `tofu init`, validation et tests simulés |
| API Proxmox HTTPS, port configuré (exemple : 8006) | Poste | Plan/apply et préparation de l'image, avec token API |
| `cloud.debian.org` en HTTPS | Nœud Proxmox | Télécharger l'image cloud Debian |
| Miroirs Debian configurés dans l'invité | VM | Index APT et paquets Docker/Compose |
| Docker Hub et ses services de distribution | VM | Tirer l'image PostgreSQL |
| Sources des règles et bases de vulnérabilités Trivy | Poste et CI | Analyses IaC, paquets et binaires ; un téléchargement échoué fait échouer le contrôle |
| SSH vers la VM, généralement port 22 | Poste | Exécution Ansible |
| DNS, passerelle et réseau privé | Poste, nœud, VM et applications | Résolution, routage et accès SQL aux ports configurés |
| GitHub Actions et artifacts | CI | Exécution et conservation des rapports sept jours |
| API GitHub Releases et assets officiels | Veille CI quotidienne | Surveiller toutes les releases stables OpenTofu/provider et les correctifs Gitleaks ; rescanner les binaires après vérification SHA-256 |
| Cache GitHub Actions | Veille CI quotidienne | Mémoriser les notifications déjà envoyées, sans secret |
| Webhook entrant `discord.com` | Veille CI quotidienne | Nouvelles versions, correctifs confirmés ou confirmation d’exécution sans nouveauté ; secret `DISCORD_WEBHOOK_URL` |

Ce tableau décrit les usages, pas une liste exhaustive de domaines à autoriser
dans un pare-feu : les registres peuvent utiliser des redirections et CDN.

## Relever les versions réellement installées

Sur le poste, depuis le dépôt, ces commandes lisent les versions sans déployer :

```sh
mise ls --installed
mise exec -- tofu version
mise exec -- ansible --version
mise exec -- ansible-galaxy collection list
mise exec -- ansible-lint --version
```

Les graphes Python exacts sont dans les chemins référencés par `mise.lock`.
Pour relever les paquets effectivement installés, utiliser aussi
`uv pip freeze --python /chemin/vers/cet/interpreteur` avec l'interpréteur de
chaque outil. Le Python du projet n'est pas forcément celui de leurs environnements.

Sur la VM, après déploiement, relever les paquets et les images en lecture seule :

```sh
dpkg-query -W -f='${binary:Package}\t${Version}\n'
docker version
docker compose version
docker image ls --digests
docker ps --format '{{.Names}}\t{{.Image}}\t{{.ID}}'
```

Les commandes Docker nécessitent les permissions adaptées sur la VM. Si le tag
a été actualisé depuis le démarrage, relever aussi l'ID d'image du conteneur
concerné avec `docker inspect --format '{{.Image}}' <conteneur>` : le digest du
tag local seul ne prouve pas quelle image tourne.

Cet inventaire n'est pas un SBOM exhaustif : les composants embarqués non
identifiables des binaires, les paquets natifs du poste et les paquets d'une VM
déployée doivent encore être collectés sur les artefacts réellement utilisés.
Les rapports Trivy incluent les paquets analysés, même sans vulnérabilité.
Le [suivi des travaux](TODO.md) prévoit une collecte plus complète. La licence du dépôt ne
remplace pas les licences propres à ces dépendances.

## Paquets Python verrouillés
Cette liste reprend tous les paquets des graphes. Les marqueurs dans les fichiers
`uv.lock` déterminent les versions retenues selon Python et la plateforme.

### ansible
Graphe : [uv.lock](.mise/locks/ansible/14.5.0~0672620e/uv.lock).

| Paquet | Version(s) |
| --- | --- |
| `ansible` | 14.5.0 |
| `ansible-core` | 2.21.5 |
| `cffi` | 2.1.1 |
| `cryptography` | 50.0.2 |
| `jinja2` | 3.1.6 |
| `markupsafe` | 3.0.4 |
| `packaging` | 26.3 |
| `pycparser` | 3.11 |
| `pyyaml` | 6.0.3 |
| `resolvelib` | 1.2.1 |

### pypi:ansible-lint
Graphe : [uv.lock](.mise/locks/pypi-ansible-lint/26.10.1/uv.lock).

| Paquet | Version(s) |
| --- | --- |
| `ansible-compat` | 26.10.0 |
| `ansible-core` | 2.16.19, 2.19.14, 2.21.5 |
| `ansible-lint` | 26.10.1 |
| `attrs` | 26.1.0 |
| `black` | 26.10.1 |
| `bracex` | 3.1 |
| `cffi` | 2.1.1 |
| `click` | 8.5.0 |
| `cryptography` | 50.0.2 |
| `distro` | 1.9.0 |
| `filelock` | 4.1.0, 4.2.4 |
| `jinja2` | 3.1.6 |
| `jsonschema` | 4.26.0 |
| `jsonschema-specifications` | 2025.9.1 |
| `markupsafe` | 3.0.4 |
| `mypy-extensions` | 1.1.0 |
| `packaging` | 26.3 |
| `pathspec` | 1.1.1 |
| `platformdirs` | 4.12.4, 4.13.5 |
| `pycparser` | 3.11 |
| `pytokens` | 0.4.1 |
| `pyyaml` | 6.0.3 |
| `referencing` | 0.37.0 |
| `resolvelib` | 1.0.1, 1.2.1 |
| `rpds-py` | 0.30.0, 2026.9.1 |
| `ruamel-yaml` | 0.19.1 |
| `subprocess-tee` | 0.4.2 |
| `tomli` | 2.5.0 |
| `typing-extensions` | 4.16.0 |
| `wcmatch` | 11.1 |
| `yamllint` | 1.38.0 |

[Présentation](README.md) · [Vérification](docs/verification.md) · [ADR](docs/adr/README.md)
