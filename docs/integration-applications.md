# Provisionnement depuis l'IaC des applications

[Documentation](README.md) · [Travaux à suivre](../TODO.md)

## Objectif après la v1

Permettre au dépôt IaC d'une application de créer sa base et son utilisateur sur
une instance PostgreSQL hébergée ici. Cette intégration est techniquement
possible avec les ressources du provider `cyrilgdn/postgresql` :
[base](https://github.com/cyrilgdn/terraform-provider-postgresql/blob/master/website/docs/r/postgresql_database.html.markdown),
[rôle](https://github.com/cyrilgdn/terraform-provider-postgresql/blob/master/website/docs/r/postgresql_role.html.markdown)
et [permissions](https://github.com/cyrilgdn/terraform-provider-postgresql/blob/master/website/docs/r/postgresql_grant.html.markdown).
La version retenue devra être épinglée et testée avec OpenTofu.

La v1 ne fournit pas encore ce module ni cette intégration. Cette piste concerne
une **base SQL dans une instance déjà démarrée**. Créer une nouvelle instance
Docker et son port nécessite aussi une opération d'orchestration dans ce projet ;
le provider PostgreSQL ne crée pas les conteneurs.

## Répartition envisagée

| Composant | Responsabilité |
| --- | --- |
| Ce dépôt | VM, Docker, instance PostgreSQL, stockage et accès de provisionnement |
| IaC de l'application | Base SQL, rôle applicatif et permissions dont elle est propriétaire |
| OpenBao commun | Secrets et politiques d'accès propres à chaque application et automatisation |
| Application | Utilisation de sa base avec ses droits d'exécution |

Le pipeline applicatif se connecte à l'instance avec son hôte, son port et une
base de maintenance existante. Il utilise un compte de provisionnement distinct
du compte d'exécution de l'application. Créer une base exige notamment
`CREATEDB` ou un superutilisateur ; créer des rôles et attribuer les droits
demande les autorisations correspondantes. `CREATEDB` est un attribut du rôle
à l'échelle de l'instance, pas une permission limitée à un préfixe de noms de bases.
Voir [CREATE DATABASE dans PostgreSQL 17](https://www.postgresql.org/docs/17/sql-createdatabase.html).

## Secrets centralisés

Les identifiants peuvent être fournis au provider sans les écrire dans le dépôt,
notamment par les variables d'environnement qu'il prend en charge. Une
automatisation authentifiée auprès d'OpenBao pourrait obtenir les secrets
autorisés puis les injecter au lancement. Cette composition est une piste
d'intégration, pas une fonctionnalité déjà configurée ici. Voir la
[configuration du provider](https://github.com/cyrilgdn/terraform-provider-postgresql/blob/master/website/docs/index.html.markdown).

Un coffre commun ne signifie pas que toutes les applications accèdent à tous
les secrets. Chaque application doit avoir sa politique d'accès. OpenBao peut
aussi gérer des identifiants PostgreSQL statiques ou dynamiques, mais il faut
choisir qui crée et fait tourner chaque rôle : OpenBao et l'IaC ne doivent pas
piloter indépendamment le même mot de passe. Voir le
[moteur PostgreSQL d'OpenBao](https://openbao.org/docs/secrets/databases/postgresql/).

La centralisation ne suffit pas à exclure les secrets des plans ou des states.
Le provider documente notamment la persistance du champ `password` des rôles.
Les mécanismes alternatifs doivent être vérifiés avec les versions retenues.

## Adaptations nécessaires

Cette approche réutilise la VM et les ports existants ; elle ne demande pas une
refonte de l'infrastructure. Elle ajoute toutefois un module applicatif, des
accès SQL adaptés, l'intégration au coffre et des tests de cycle de vie. La
protection du transport doit être prévue : la v1 ne configure pas TLS PostgreSQL.

Une ressource SQL doit avoir un seul propriétaire et un seul state de gestion.
Si l'application reprend une base initialisée par `POSTGRES_DB`, il faut prévoir
sa reprise explicite, notamment un import si elle est suivie par le provider,
plutôt que tenter de la recréer. Les métadonnées de ce contrat peuvent être
transmises sans donner au projet applicatif accès au state complet de la VM.

Enfin, plusieurs applications partageant une même instance partagent son cycle
serveur. Pour conserver l'indépendance décrite dans l'[ADR 0004](adr/0004-compose-par-instance.md),
chaque application doit cibler son instance dédiée. Les travaux de validation
et de mise en œuvre figurent dans [TODO.md](../TODO.md#provisionnement-depuis-liac-des-applications).
