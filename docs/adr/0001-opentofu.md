# ADR 0001 — Utiliser OpenTofu

Statut : implémenté en v1.

## Contexte

La VM et l'image Debian doivent être décrites, versionnées et suivies via l'API
Proxmox. Le projet vise à garder la maîtrise de son infrastructure et de ses
outils, en privilégiant les logiciels libres. Il doit aussi pouvoir évoluer vers
un déploiement automatisé et accueillir d'autres providers si les besoins dépassent
Proxmox.

## Alternatives

- OpenTofu : outil IaC libre sous MPL-2.0, avec configuration déclarative, plan, state et providers.
- Terraform : modèle technique comparable, mais versions récentes sous BSL 1.1, avec des restrictions d'usage supplémentaires.
- Scripts appelant directement les API : contrôle détaillé des opérations, mais logique de suivi des ressources, de comparaison et d'ordonnancement à développer et maintenir.

## Décision et justification

Retenir OpenTofu en priorité pour sa liberté d'utilisation et sa gouvernance
communautaire au sein de la Linux Foundation. Ce choix répond à l'objectif de
souveraineté du projet : conserver la possibilité d'exécuter, d'étudier, de
modifier et de redistribuer l'outil selon une licence libre, sans dépendre d'un
service d'exécution imposé par un éditeur. Voir la
[licence MPL-2.0 d'OpenTofu](https://github.com/opentofu/opentofu/blob/main/LICENSE)
et son [manifeste](https://opentofu.org/manifesto/).

La BSL de Terraform autorise l'usage interne, y compris en production, mais
restreint certaines offres commerciales concurrentes hébergées ou embarquées.
Terraform pourrait donc convenir à cet usage de homelab ; OpenTofu est préféré
pour les libertés qu'offre sa licence et pour l'autonomie recherchée à long terme.
Voir la [licence de Terraform](https://github.com/hashicorp/terraform/blob/main/LICENSE).

Le modèle déclaratif évite de réimplémenter dans des scripts toute la gestion
du cycle de vie : état des ressources, calcul des changements, dépendances et
plan avant application. Pour ce projet, construire et maintenir ces mécanismes
serait plus lourd que s'appuyer sur un moteur IaC existant. Les scripts restent
utiles pour les opérations complémentaires, comme la préparation de l'image.
Ce raisonnement s'appuie sur le
[fonctionnement d'OpenTofu](https://opentofu.org/docs/intro/).

À terme, ce même modèle doit faciliter un pipeline de déploiement dans GitHub
Actions ou un autre système de CI : validation, génération d'un plan, puis
application du plan retenu. OpenTofu et Terraform conviennent à ce type
d'automatisation ; la licence et la gouvernance font pencher le choix vers
OpenTofu. Sa CLI permet notamment de séparer le plan de son application,
comme décrit dans la [documentation de `tofu apply`](https://opentofu.org/docs/v1.13/cli/commands/apply/).

OpenTofu est compatible avec l'écosystème des providers Terraform et dispose
de son propre registre. Il permet donc d'envisager l'ajout de providers cloud
sans changer de moteur IaC. La disponibilité et la compatibilité des versions
retenues doivent être vérifiées pour chaque ajout ; il ne s'agit pas d'une
garantie de compatibilité universelle avec toutes les évolutions futures.
Voir la [FAQ sur les providers](https://opentofu.org/faq/).

## Conséquences

Le state devient un fichier à protéger et sauvegarder. Les contrôles utilisent
`tofu`, y compris ses tests avec provider simulé. Le provider `bpg/proxmox` est
épinglé et son verrou est versionné. Le dossier conserve le nom `terraform/`,
référencé dans les commandes et la documentation. L'exécution de ce dépôt avec
Terraform n'est pas testée.

La v1 utilise uniquement Proxmox. Ajouter un cloud demanderait des ressources,
des accès et des tests adaptés ; les ressources Proxmox ne deviennent pas
automatiquement portables vers un autre provider.

La CI actuelle exécute les contrôles sans déployer. Un futur pipeline de
déploiement devra gérer la persistance et le verrouillage du state, les secrets,
l'accès réseau à Proxmox et les validations avant application. Le choix
d'OpenTofu préserve l'autonomie de l'outillage ; l'hébergement de la CI et les
services externes utilisés restent des choix distincts.

## Réexamen

Revoir ce choix si les besoins d'équipe, le support du provider ou une plateforme
d'exécution imposent un autre outil. Toute migration doit tester le state et le
plan sur une copie de test avant une application réelle.

## Références

- [OpenTofu : fonctionnement et cycle plan/apply](https://opentofu.org/docs/intro/).
- [Manifeste OpenTofu](https://opentofu.org/manifesto/).
- [Licence OpenTofu : MPL-2.0](https://github.com/opentofu/opentofu/blob/main/LICENSE).
- [Licence Terraform : BSL 1.1 et conditions d'usage](https://github.com/hashicorp/terraform/blob/main/LICENSE).
- [FAQ OpenTofu : écosystème et compatibilité des providers](https://opentofu.org/faq/).
- [OpenTofu : application d'un plan enregistré](https://opentofu.org/docs/v1.13/cli/commands/apply/).
- Code : [versions.tf](../../terraform/versions.tf), [Makefile](../../Makefile).

[Index des ADR](README.md)
