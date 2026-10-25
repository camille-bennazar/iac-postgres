# Décisions d'architecture

Ces ADR (Architecture Decision Records) consignent les décisions prises dès la
conception du projet et appliquées dans la v1.

Chaque décision précise le contexte, les alternatives, le choix retenu, ses
conséquences et les conditions qui justifieraient de la réexaminer. Le statut
« Implémenté en v1 » décrit le code existant ; il ne vaut pas recette en production.

| ADR | Décision | Statut |
| --- | --- | --- |
| [0001](0001-opentofu.md) | OpenTofu plutôt que Terraform | Implémenté en v1 |
| [0002](0002-vm-plutot-que-lxc.md) | Une VM Debian plutôt qu'un conteneur LXC | Implémenté en v1 |
| [0003](0003-provisionnement-et-configuration.md) | Séparer OpenTofu, cloud-init et Ansible | Implémenté en v1 |
| [0004](0004-compose-par-instance.md) | Un projet Compose par instance sur une VM partagée | Implémenté en v1 |
| [0005](0005-state-local.md) | Conserver le state local pour un usage individuel | Implémenté en v1 |
| [0006](0006-secrets-et-initialisation.md) | Secrets en fichiers et initialisation explicite | Implémenté en v1 |

Lorsqu'un choix change, ajouter un nouvel ADR et relier les deux décisions.
Conserver l'ancien document pour expliquer le contexte antérieur. Les évolutions
envisagées sont dans [TODO.md](../../TODO.md).

[Architecture](../architecture.md) · [Documentation](../README.md)
