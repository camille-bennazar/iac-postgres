# ADR 0005 — Conserver un state local

Statut : implémenté en v1.

## Contexte

Le projet s'exécute depuis le poste d'un opérateur pour gérer une VM. Aucun
backend distant ni compte de stockage partagé n'est configuré.
À terme, le state doit pouvoir être partagé entre plusieurs postes ou utilisé
par une CI de déploiement, en privilégiant une solution libre et auto-hébergée.

## Alternatives

- State local : peu de prérequis, sauvegarde et coordination à la charge de l'opérateur.
- Backend distant : partage possible et mécanismes de verrouillage selon le backend, avec un service et des accès supplémentaires.
- State versionné avec le code : écarté, car il expose des informations d'infrastructure et ne fournit pas une coordination adaptée.

## Décision et justification

Conserver le state dans `terraform/`, ignoré par Git. Les commandes Make sont
sérialisées par un verrou local. Le nettoyage archive le state et bloque les
opérations d'infrastructure tant qu'il n'a pas été restauré.

Ce choix limite les services nécessaires pour la v1. Il constitue un point de
départ, avec une évolution envisagée vers un backend distant auto-hébergé lorsque
les besoins de collaboration ou d'automatisation le justifieront.

## Évolution vers un backend distant

Étudier en priorité [Garage](https://garagehq.deuxfleurs.fr/), un stockage objet
auto-hébergé exposant une API compatible S3, pour conserver le state via le
[backend S3 d'OpenTofu](https://opentofu.org/docs/language/settings/backends/s3/).
Cette piste répond à l'objectif de maîtrise du stockage sans imposer un service
cloud externe. Le backend HTTP reste une alternative si la solution retenue
implémente son protocole et le verrouillage nécessaire.

La compatibilité S3 ne garantit pas à elle seule le verrouillage du state :
OpenTofu utilise notamment des écritures conditionnelles `If-None-Match` pour
son verrou S3 natif. Leur prise en charge et leur comportement en concurrence
doivent être vérifiés sur la version de Garage retenue, à partir de sa
[documentation de compatibilité](https://garagehq.deuxfleurs.fr/documentation/reference-manual/s3-compatibility/)
et de tests. Le choix final reste conditionné à cette validation.

Prévoir également le contrôle d'accès, la protection du state, ses sauvegardes
et sa restauration. La réplication des objets ne remplace pas un historique
restaurable après une suppression ou une mauvaise écriture.

Ces travaux sont suivis dans [TODO.md](../../TODO.md). Aucun backend distant
n'est déployé par la v1.

## Conséquences

Le dépôt seul ne suffit pas à reprendre la gestion d'une VM existante : il
faut restaurer son state ou préparer un import. Les archives locales ne sont
pas des sauvegardes indépendantes et ne contiennent pas les données SQL.
Le verrou du projet ne coordonne pas plusieurs postes ; les appels directs
aux outils contournent ses protections. Le state n'est pas chiffré par le projet.

## Réexamen

Passer à un backend adapté avant des opérations depuis plusieurs postes ou
une CI de déploiement. Tester la migration, la restauration et le verrouillage,
sans perdre l'association entre ressources et state. Adapter aussi les scripts
de nettoyage et de restauration, dont les protections actuelles reposent sur
un state local. Le service de state doit rester disponible pour reprendre
l'infrastructure qu'il suit, y compris après la perte de la VM PostgreSQL.

## Références

- [Backend OpenTofu S3](https://opentofu.org/docs/language/settings/backends/s3/).
- [Backend OpenTofu HTTP](https://opentofu.org/docs/language/settings/backends/http/).
- [Garage : stockage objet S3 auto-hébergé](https://garagehq.deuxfleurs.fr/).
- [Compatibilité S3 de Garage](https://garagehq.deuxfleurs.fr/documentation/reference-manual/s3-compatibility/).
- Code : [maintenance.py](../../scripts/maintenance.py), [Makefile](../../Makefile).
- [Maintenance du state](../maintenance.md#state-local).

[Index des ADR](README.md)
