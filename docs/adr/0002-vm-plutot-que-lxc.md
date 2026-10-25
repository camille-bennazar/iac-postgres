# ADR 0002 — Héberger Docker dans une VM Debian

Statut : implémenté en v1.

## Contexte

Proxmox propose des VM et des conteneurs LXC. La cible du projet doit exécuter
Docker et plusieurs instances PostgreSQL sans installer ces services sur l'hôte.
La priorité est de protéger l'hyperviseur et les autres charges du homelab si
une application, un conteneur ou le démon Docker est compromis.

## Alternatives

- VM QEMU/KVM : noyau invité distinct et frontière de virtualisation, avec le coût d'un système complet.
- LXC : système plus léger partageant le noyau de l'hôte ; Docker imbriqué demande des fonctionnalités et permissions adaptées.
- Installation sur l'hôte Proxmox : moins de couches, mais mélange des services applicatifs et de l'hyperviseur.

## Décision et justification

Créer une VM Debian 13 à partir de l'image cloud officielle, en privilégiant
l'isolation de l'hyperviseur plutôt que le gain de ressources d'un LXC.

Un LXC partage le noyau Proxmox. Docker exécuté dans ce LXC utilise donc lui
aussi ce noyau : imbriquer les conteneurs n'ajoute pas de noyau indépendant.
Dans une VM, Docker utilise le noyau invité ; la frontière QEMU/KVM sépare
cet environnement de l'hôte. Proxmox recommande cette organisation lorsque
l'isolation est prioritaire. Voir la
[documentation sur les conteneurs](https://github.com/proxmox/pve-docs/blob/master/pct.adoc).

Docker dans un LXC non privilégié nécessite notamment `keyctl` selon la
documentation Proxmox. L'option `nesting`, destinée aux conteneurs imbriqués,
expose davantage de contenu de `procfs` et `sysfs`. Ces options élargissent
les interfaces accessibles sans donner automatiquement les droits root sur
l'hyperviseur. Voir les
[options LXC de Proxmox](https://github.com/proxmox/pve-docs/blob/master/generated/pct.conf.5-opts.adoc).

Le choix vise à limiter les conséquences d'une compromission de Docker au
périmètre de la VM. Docker dépend des protections du noyau et son démon dispose
par défaut de privilèges élevés sur son système d'exécution. Une faille ou une
mauvaise configuration peut affaiblir cette isolation, comme l'explique la
[documentation de sécurité Docker](https://docs.docker.com/engine/security/).

L'évolution des capacités offensives assistées par IA renforce cette priorité.
Le NCSC estime que l'IA peut accélérer la recherche de vulnérabilités et leur
exploitation. Cette évaluation soutient une approche de défense en profondeur ;
elle ne démontre pas une hausse générale des failles LXC causée par l'IA.
Voir son [évaluation de la menace à l'horizon 2027](https://www.ncsc.gov.uk/report/impact-ai-cyber-threat-now-2027).

## Conséquences

Il faut allouer RAM et disque à un OS complet, maintenir Debian et attendre
cloud-init. Ce coût est accepté pour renforcer la séparation avec l'hyperviseur.
Toutes les bases restent dépendantes de cette unique VM. Le projet ne mesure
pas le surcoût par rapport à LXC. Le guest agent QEMU est désactivé dans la
configuration actuelle.

La VM ajoute une frontière de sécurité, sans garantir l'impossibilité d'une
évasion : l'hyperviseur et les périphériques virtualisés restent une surface
d'attaque. Les mises à jour de Proxmox, de Debian et de Docker restent nécessaires,
ainsi que le filtrage réseau. Cette séparation ne bloque pas à elle seule les
accès réseau de la VM aux services d'administration de l'hôte.

## Réexamen

Réévaluer LXC si la consommation de ressources devient déterminante, après un
examen explicite du niveau d'isolation acceptable et un essai documenté des
permissions, du stockage, des sauvegardes et des mises à jour.

## Références

- [Documentation Proxmox : conteneurs et isolation](https://github.com/proxmox/pve-docs/blob/master/pct.adoc).
- [Options LXC : `keyctl` et `nesting`](https://github.com/proxmox/pve-docs/blob/master/generated/pct.conf.5-opts.adoc).
- [Sécurité Docker : noyau, privilèges et démon](https://docs.docker.com/engine/security/).
- [NCSC : impact de l'IA sur la menace cyber à l'horizon 2027](https://www.ncsc.gov.uk/report/impact-ai-cyber-threat-now-2027).
- Code : [main.tf](../../terraform/main.tf), [image.tf](../../terraform/image.tf).

[Index des ADR](README.md)
