# Documentation

Cette documentation décrit le fonctionnement actuel du projet. Les chemins et les
commandes sont donnés depuis la racine du dépôt, même lorsque le guide se trouve
dans `docs/`.

## Premier déploiement

1. Vérifier les prérequis et préparer les outils avec le [guide d'installation](installation.md).
2. Renseigner les fichiers avec la [référence de configuration](configuration.md).
3. Créer le token et attribuer les droits avec le [guide Proxmox](proxmox.md).
4. Reprendre le guide d'installation pour vérifier et déployer.

## Guides

| Guide | Contenu |
| --- | --- |
| [Installation](installation.md) | Prérequis, préparation locale et premier déploiement |
| [Accès Proxmox](proxmox.md) | Utilisateur, token API, rôles et chargement du secret |
| [Configuration](configuration.md) | Variables d'infrastructure et entrées PostgreSQL |
| [Utilisation](utilisation.md) | Commandes existantes, ajout d'une instance et connexion |
| [Maintenance](maintenance.md) | State, fichiers générés, image Debian et vérifications |
| [Dépannage](depannage.md) | Erreurs d'accès, SSH, validation et conteneurs |
| [Sécurité](securite.md) | Risques connus, correctifs et exceptions Trivy |
| [Vérification](verification.md) | Versions, CI GitHub et limites des contrôles |
| [Architecture](architecture.md) | Schémas Mermaid, flux et responsabilités |
| [Décisions d'architecture](adr/README.md) | Choix de conception de la v1, alternatives et conséquences |
| [Intégration des applications](integration-applications.md) | Évolution envisagée pour provisionner des bases depuis une IaC applicative |
| [Dépendances](../DEPENDENCIES.md) | Inventaire des outils, systèmes et services externes |
| [Travaux à suivre](../TODO.md) | Évolutions envisagées après la v1 |

Les opérations se lancent avec `make <cible>`. mise fournit les versions des
outils ; si elles ne sont pas activées dans le shell, utiliser
`mise exec -- make <cible>`.

[Présentation du projet](../README.md)
