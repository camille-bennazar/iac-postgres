# ADR 0006 — Fournir les secrets par fichiers

Statut : implémenté en v1.

## Contexte

Les mots de passe ne doivent apparaître ni dans le dépôt ni dans les sorties
Ansible. Le rendu Compose doit préserver leurs caractères spéciaux.

## Alternatives

- Injecter le mot de passe dans le YAML Compose ou une variable d'environnement : simple, mais multiplie les occasions de copie ou d'interpolation.
- Utiliser un fichier secret Compose : compatible avec l'initialisation de l'image PostgreSQL et le fonctionnement local retenu.
- Intégrer un coffre ou des fichiers chiffrés : protection et gestion supplémentaires, avec un service ou des clés à administrer.

## Décision et justification

Conserver la configuration privée locale dans `databases.yml`, ignoré par Git
et protégé en `0600`. Ansible écrit un fichier root en `0600` par instance et le
fournit à Compose. Le conteneur le lit via `POSTGRES_PASSWORD_FILE` ; les tâches
sensibles utilisent `no_log`. Le token Proxmox est chargé dans l'environnement
du terminal et n'est pas écrit dans les variables OpenTofu du projet.

## Conséquences

Les secrets Compose sont des fichiers montés dans les conteneurs, sans coffre
ni chiffrement automatique au repos. Les mots de passe restent lisibles par les
administrateurs autorisés du poste et de la VM. `no_log` et `.gitignore` réduisent
les expositions accidentelles, sans remplacer la protection de ces machines.

Les variables d'initialisation de l'image PostgreSQL s'appliquent à un répertoire
de données vide. Changer le fichier de mot de passe ou les champs YAML ne réalise
pas une rotation SQL sur une base existante.

En v1, le seul utilisateur de connexion provisionné par le projet est celui
défini par `POSTGRES_USER` : le superutilisateur initial de chaque instance.
Aucun utilisateur dédié à l'application ni aucune politique de permissions
applicatives n'est créé automatiquement. Les rôles système internes de PostgreSQL
ne constituent pas des comptes applicatifs supplémentaires.

## Évolution des comptes applicatifs

Prévoir un utilisateur dédié à chaque application, distinct du compte
d'administration et sans privilège de superutilisateur. Ses permissions devront
être définies selon les besoins sur la base, les schémas, les tables et les
séquences, avec des privilèges par défaut adaptés aux futurs objets. Les droits
de migration de schéma devront être séparés des droits d'exécution lorsque
l'application le permet.

Ce provisionnement devra aussi fonctionner sur une instance déjà initialisée,
via des opérations SQL explicites plutôt que les seules variables d'initialisation
Docker. Sa mise en œuvre et les tests de permissions sont suivis dans
[TODO.md](../../TODO.md).

## Évolution vers un coffre auto-hébergé

Étudier [OpenBao](https://openbao.org/docs/what-is-openbao/) pour centraliser les
secrets et contrôler leur accès depuis les postes des opérateurs et une future
CI de déploiement. OpenBao fournit une gestion des secrets et des services de
chiffrement avec authentification, politiques d'accès et audit.

L'intégration devra définir comment Ansible récupère et fournit les secrets aux
instances, avec des droits limités et sans exposition dans les journaux. Elle
devra aussi prévoir la sauvegarde et la restauration du coffre ainsi que la
rotation des accès. Centraliser un mot de passe ne réalise pas à lui seul sa
rotation dans PostgreSQL.

Ce travail est suivi dans [TODO.md](../../TODO.md). La v1 conserve les fichiers
privés et les secrets Compose ; elle ne déploie pas OpenBao.

## Réexamen

Introduire chiffrement ou coffre si les secrets doivent circuler entre opérateurs,
et une procédure SQL dédiée pour la rotation ou les rôles applicatifs.

## Références

- [Secrets Docker Compose](https://docs.docker.com/compose/how-tos/use-secrets/).
- [Initialisation de l'image PostgreSQL](https://hub.docker.com/_/postgres).
- [OpenBao : gestion des secrets et chiffrement](https://openbao.org/docs/what-is-openbao/).
- Code : [deploy-instance.yml](../../ansible/tasks/deploy-instance.yml), [auth.sh](../../scripts/auth.sh).

[Index des ADR](README.md)
