# ADR 0003 — Séparer infrastructure et configuration système

Statut : implémenté en v1.

## Contexte

Créer la VM et ajouter une instance PostgreSQL sont deux opérations de cycles
de vie différents. Un ajout de base ne doit pas nécessiter de recréer la VM.

## Alternatives

- Tout embarquer dans cloud-init : amorçage concentré, mais reconfiguration applicative moins pratique.
- Utiliser des provisioners et commandes SSH depuis l'IaC : orchestration centrale, mais couplage de la configuration au cycle du state.
- Séparer OpenTofu et Ansible : deux outils à maintenir, avec une frontière explicite.

## Décision et justification

OpenTofu gère l'image, la VM, les ressources et la configuration cloud-init
initiale (réseau et compte SSH). Ansible attend cloud-init, installe Docker et
applique les projets Compose. L'inventaire JSON est généré depuis les sorties
OpenTofu, sans recopier manuellement l'IP dans un inventaire versionné.

## Conséquences

`configure` réapplique Ansible sur la VM existante ; `apply` gère l'infrastructure.
Les deux couches restent nécessaires et une erreur Ansible après `apply` ne
supprime pas la VM créée. La CI valide séparément les configurations, sans
prouver leur fonctionnement de bout en bout sur Proxmox.

## Réexamen

Revoir la frontière si une image système préconstruite remplace la configuration
Ansible, ou si une plateforme gère directement le cycle des services applicatifs.

## Références

Code : [outputs.tf](../../terraform/outputs.tf), [deploy.yml](../../ansible/deploy.yml),
[Makefile](../../Makefile). Voir le [schéma des opérations](../architecture.md).

[Index des ADR](README.md)
