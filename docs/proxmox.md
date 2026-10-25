# Accès à Proxmox

[Documentation](README.md) · [Installation](installation.md)

Cette procédure prépare l’accès API utilisé par OpenTofu et le script de
réutilisation de l’image Debian. Elle ne crée pas la VM. Choisir les valeurs de
[configuration](configuration.md) avant d’attribuer les permissions.

## 1. Sur Proxmox : créer l'utilisateur et le token

Dans l'interface Proxmox, se connecter en administrateur, sélectionner le nœud,
puis **Shell**. Exécuter ces commandes en `root`, une seule fois :

```sh
pveum user add iac-postgres@pve --enable 1 --comment 'Provisionnement PostgreSQL'
pveum user token add iac-postgres@pve opentofu --privsep 1
```

La seconde commande affiche `full-tokenid` (`iac-postgres@pve!opentofu`) et
`value` (le secret). Enregistrer immédiatement `value` dans un gestionnaire de
mots de passe : Proxmox ne l'affichera plus. Aucun mot de passe utilisateur n'est
nécessaire pour cette authentification par token.

## 2. Sur Proxmox : attribuer les permissions

Toujours dans le Shell Proxmox en `root`, créer les rôles dédiés :

```sh
pveum role add IaCPostgresNode --privs 'Sys.Audit Sys.AccessNetwork'
pveum role add IaCPostgresImage --privs 'Datastore.Audit Datastore.AllocateTemplate'
pveum role add IaCPostgresDisk --privs 'Datastore.Audit Datastore.AllocateSpace'
pveum role add IaCPostgresVM --privs 'VM.Allocate VM.Audit VM.PowerMgmt VM.Config.CPU VM.Config.Memory VM.Config.Disk VM.Config.CDROM VM.Config.Network VM.Config.Cloudinit VM.Config.Options VM.Config.HWType'
pveum role add IaCPostgresNetwork --privs 'SDN.Use'
```

Adapter les cinq valeurs suivantes à `terraform/terraform.tfvars`, puis attribuer les
rôles **à l'utilisateur et au token** (la séparation des privilèges reste activée) :

```sh
PG_NODE=pve
PG_VM_ID=200
PG_IMAGE_STORAGE=local
PG_DISK_STORAGE=local-lvm
PG_BRIDGE=vmbr0

grant_pg_role() {
  pveum acl modify "$1" --roles "$2" --propagate 1 \
    --users iac-postgres@pve --tokens 'iac-postgres@pve!opentofu'
}

grant_pg_role "/nodes/$PG_NODE" IaCPostgresNode
if [ "$PG_IMAGE_STORAGE" = "$PG_DISK_STORAGE" ]; then
  grant_pg_role "/storage/$PG_IMAGE_STORAGE" IaCPostgresImage,IaCPostgresDisk
else
  grant_pg_role "/storage/$PG_IMAGE_STORAGE" IaCPostgresImage
  grant_pg_role "/storage/$PG_DISK_STORAGE" IaCPostgresDisk
fi
grant_pg_role "/vms/$PG_VM_ID" IaCPostgresVM
grant_pg_role "/sdn/zones/localnetwork/$PG_BRIDGE" IaCPostgresNetwork
```

Vérifier les **droits effectifs**, au-delà de la présence des ACL :

```sh
pveum user permissions iac-postgres@pve --path "/vms/$PG_VM_ID"
pveum user token permissions iac-postgres@pve opentofu --path "/vms/$PG_VM_ID"
pveum user token permissions iac-postgres@pve opentofu --path "/nodes/$PG_NODE"
pveum user token permissions iac-postgres@pve opentofu --path "/storage/$PG_IMAGE_STORAGE"
pveum user token permissions iac-postgres@pve opentofu --path "/storage/$PG_DISK_STORAGE"
```

Les sorties sur la VM doivent inclure `VM.Audit`, `VM.Allocate` et les autres
privilèges du rôle `IaCPostgresVM`. Vérifier `Sys.Audit` et `Sys.AccessNetwork`
sur le nœud, ainsi que les droits des rôles de stockage sur leurs chemins.
Les droits d'un token séparé sont l'intersection des droits de l'utilisateur
et de ses propres ACL.

En cas de refus `403`, consulter le [dépannage des permissions](depannage.md#permissions-proxmox-refusées-http-403).

Le droit `VM.Allocate` sur `/vms/<ID>` permet de créer la VM même si elle n'existe
pas encore. Les permissions restent limitées à cette VM, au nœud, aux stockages
et au bridge choisis ; aucune ACL n'est attribuée à la racine du cluster.
`Sys.Audit` permet les lectures du nœud et `Sys.AccessNetwork` autorise la requête
de métadonnées et le téléchargement HTTPS effectués par Proxmox. Ce dernier
droit permet aussi au détenteur du token de faire émettre des requêtes réseau
par le nœud : protéger le token et limiter les sorties réseau de l'hyperviseur.

Le projet exige une version de Proxmox VE 9 prenant en charge `Sys.AccessNetwork`
pour `query-url-metadata` et `download-url`. Vérifier ce prérequis dans l'API Viewer
de l'installation. Les droits de stockage distinguent le téléchargement de
l'image de l'allocation des disques ; ils sont cumulés si le stockage est commun.
Les ACL restent à valider sur l'environnement de test avec le plan et le déploiement.
Voir les [permissions de téléchargement](https://github.com/proxmox/pve-storage/blob/master/src/PVE/API2/Storage/Status.pm)
et les [permissions des métadonnées](https://github.com/proxmox/pve-manager/blob/master/PVE/API2/Nodes.pm).

## 3. Sur le PC : exporter le token dans le terminal de déploiement

Revenir dans le terminal **Bash du PC**, à la racine du projet :

```sh
source scripts/auth.sh
```

Saisir l'identifiant complet du token, ou Entrée pour accepter
`iac-postgres@pve!opentofu`, puis coller uniquement le secret `value`.
La saisie du secret est masquée. Le script exporte `PROXMOX_VE_API_TOKEN` dans
le terminal actuel au format `utilisateur@realm!nom-du-token=secret`.
Il ne crée aucun fichier et masque ses opérations sensibles même avec `set -x`.
Une saisie vide, invalide ou interrompue par une fin d'entrée ne remplace pas
un token précédemment chargé.

Le script doit être **sourcé**, pas exécuté avec `bash` ou Make : un processus
enfant ne peut pas modifier l'environnement du terminal parent. `make auth`
rappelle la commande à utiliser. Ce script vise Bash, pas Fish ou Zsh.

Le secret saisi n'est pas ajouté à l'historique. La variable est transmise aux
commandes du projet lancées depuis ce terminal ; refaire cette étape dans un
nouveau terminal. Ne pas la mettre dans `terraform/terraform.tfvars` : le
provider lit directement `PROXMOX_VE_API_TOKEN`. Un fichier `.env` n'est pas
chargé automatiquement. Retirer le token avec :

```sh
unset PROXMOX_VE_API_TOKEN
```

Après avoir renseigné la [configuration](configuration.md), `make plan` vérifie
l'accès API sans créer la VM. Une erreur `401` indique généralement un token
incorrect, expiré ou désactivé ; une erreur `403` demande de vérifier les ACL de
l'utilisateur **et** du token sur le chemin mentionné. Pour retirer le token du
terminal : `unset PROXMOX_VE_API_TOKEN`.

