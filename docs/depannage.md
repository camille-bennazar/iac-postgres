# Dépannage

[Documentation](README.md)

Les commandes locales ci-dessous se lancent depuis la racine du projet. Les
commandes Proxmox s'exécutent dans son Shell administrateur ; les commandes
Docker s'exécutent sur la VM PostgreSQL.

## Token absent ou authentification refusée (HTTP 401)

Recharger le token dans le même terminal que celui utilisé pour mise, selon le
[guide Proxmox](proxmox.md). La valeur attendue est
`utilisateur@realm!nom-du-token=secret`. Ne pas afficher le secret pour la vérifier.
Un fichier `.env` n'est pas chargé automatiquement.

Une réponse `401` peut indiquer un token incorrect, expiré ou désactivé.
Vérifier son identité et son état dans Proxmox.

## Permissions Proxmox refusées (HTTP 403)

Une ACL doit couvrir le chemin cité par l'erreur et être attribuée à l'utilisateur
ainsi qu'au token avec séparation des privilèges. Vérifier les droits effectifs,
pas seulement la présence des ACL.

Pour une erreur sur `/vms/200`, adapter l'identifiant puis vérifier dans le Shell
Proxmox administrateur :

```sh
PG_VM_ID=200
pveum user permissions iac-postgres@pve --path "/vms/$PG_VM_ID"
pveum user token permissions iac-postgres@pve opentofu --path "/vms/$PG_VM_ID"
pveum acl list
```

Contrôler les attributions du [guide Proxmox](proxmox.md#2-sur-proxmox--attribuer-les-permissions),
les chemins de la VM, du nœud, des stockages et du bridge, ainsi qu'une éventuelle
ACL `NoAccess`. L'installation doit proposer `Sys.AccessNetwork` pour les appels
réseau du nœud. Le token de déploiement ne peut pas s'attribuer des permissions.

## Connexion HTTPS ou certificat refusé

Vérifier l'URL `proxmox_endpoint`, l'accès réseau et la confiance dans le certificat.
Installer la CA Proxmox sur le PC ou utiliser un certificat reconnu.
`proxmox_insecure = true` désactive explicitement cette vérification pour Proxmox.
Le script refuse HTTP et les redirections, afin de ne pas transmettre le token
à une autre URL.

## Connexion SSH impossible

Vérifier que la VM est démarrée, que son IP est joignable et que le port SSH est
accessible. Le compte doit correspondre à `ssh_user` et la clé privée à
`ssh_public_key`. Utiliser `ssh-agent` ou `ANSIBLE_PRIVATE_KEY_FILE` pour fournir
la clé privée.

Ansible attend jusqu'à 600 secondes la disponibilité de SSH et Python, puis
attend la fin de cloud-init. Une VM qui ne peut pas accéder aux dépôts peut
rester bloquée pendant son initialisation ou l'installation des paquets.

Une clé hôte inconnue est acceptée au premier accès ; une clé connue modifiée
est refusée. Après une recréation de VM, vérifier son identité avant de mettre
à jour l'entrée correspondante dans `known_hosts`.

## Inventaire absent ou sortie OpenTofu invalide

`configure` et `status` régénèrent `inventory.json` depuis le state local. Vérifier
que le déploiement de l'infrastructure a terminé et que le state se trouve dans
`terraform/`. L'inventaire n'est pas une configuration à renseigner manuellement.

Si le state a été supprimé alors que la VM existe, consulter la
[maintenance du state](maintenance.md#state-local) avant de relancer un déploiement.

## Configuration YAML refusée

Les erreurs indiquent l'index et le champ concernés sans afficher les valeurs
sensibles. `databases[0]` désigne la première entrée.

Vérifier les [contraintes de configuration](configuration.md) : identifiants,
port entier sans guillemets, doublons et secret d'au moins 20 caractères sans
marqueur d'exemple. Puis lancer :

```sh
mise exec -- make check-local
```

## Échec d'un conteneur ou port déjà utilisé

Commencer par `make status`. Un conteneur retiré du YAML peut encore occuper
son port. La validation locale détecte les doublons du YAML, pas les ports occupés
par des conteneurs absents de ce fichier.

Les tâches de déploiement masquent leurs sorties pour protéger les secrets.
Pour inspecter une instance sur la VM, adapter `app` à son identifiant :

```sh
sudo docker compose -f /opt/postgres/app/compose.yml ps -a
sudo docker compose -f /opt/postgres/app/compose.yml logs --tail=100 postgres
```

Vérifier aussi l'accès à Docker Hub, l'espace disque et la mémoire disponible.
Examiner les journaux avant de les partager : ils peuvent contenir des données
liées aux applications.

## Mot de passe modifié mais connexion refusée

`POSTGRES_DB`, `POSTGRES_USER` et le secret servent à l'initialisation d'un volume
vide. Modifier le YAML ne met pas à jour les comptes d'une base déjà initialisée.
Effectuer la rotation SQL avec les accès existants, puis synchroniser la
configuration. Ne pas supprimer le volume pour changer un mot de passe.

## Le provider ne démarre pas pendant la validation

Si `tofu validate` échoue en chargeant le schéma avec un message comme
`failed to instantiate provider` ou `Unrecognized remote plugin message`,
vérifier les versions installées et l'initialisation :

```sh
mise install
mise exec -- make init
```

Un environnement restreint peut aussi empêcher le démarrage du provider ou
l'ouverture de ses sockets locaux. Relancer la validation sur le PC de déploiement
pour distinguer une restriction d'exécution d'un problème de provider.
Les contrôles `check-local` restent indépendants du provider, mais ne remplacent
pas la validation OpenTofu.

## State archivé ou commande déjà en cours

Si une commande signale « State archivé », utiliser `make restore` pour lister
les archives puis `make restore ARCHIVE=<identifiant>`. Ne pas purger l'archive
pour contourner le blocage. Voir le [nettoyage](maintenance.md#nettoyage-et-restauration).

Si une autre commande détient le verrou, attendre sa fin. La présence du fichier
`.project.lock` seul n'indique pas un verrou actif et il ne faut pas le supprimer
pendant une opération. Un appel direct à OpenTofu peut aussi créer un verrou de
state ; le nettoyage refuse alors de déplacer les fichiers.

## Outil de contrôle absent ou mise install impossible

Lancer `mise install` avec un accès aux sources des outils. Un échec de résolution
DNS ou de téléchargement laisse les contrôles concernés non validés.
`make check-local` peut être lancé avec les outils déjà disponibles mais ne
remplace ni le lint complet ni les validations OpenTofu. Les versions de
référence sont décrites dans le [guide de vérification](verification.md#versions-des-outils).
