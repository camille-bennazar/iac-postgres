# ADR 0004 — Un projet Compose par instance PostgreSQL

Statut : implémenté en v1.

## Contexte

Plusieurs applications et environnements de développement partagent les
ressources limitées d'un homelab. Chaque entrée YAML doit avoir son port,
ses identifiants et ses données. Les applications doivent pouvoir avoir des
cycles de maintenance distincts, ainsi que leurs propres extensions et services
de supervision à terme.

## Alternatives

- Une instance PostgreSQL avec plusieurs bases et rôles : moins de processus, mais cycle serveur commun et gestion SQL à ajouter.
- Une VM par application : séparation plus forte, au prix de systèmes supplémentaires à maintenir.
- Un orchestrateur comme Kubernetes : pertinent pour d'autres besoins, mais davantage de composants pour cette cible à une VM.
- Un projet Compose par entrée : unités simples et distinctes sur le même hôte Docker.

## Décision et justification

Déployer une instance PostgreSQL 17 par entrée de `databases.yml`, avec son projet
Compose, son réseau et son volume nommé. Publier son port sur l'IPv4 de la VM.
Utiliser les paquets Docker et Compose de Debian pour garder une seule source
de paquets système dans le provisionnement actuel.

Cette séparation découple le cycle de vie des serveurs PostgreSQL : arrêter ou
redémarrer l'instance d'une application ne nécessite pas d'arrêter les instances
des autres applications. Avec un serveur PostgreSQL unique hébergeant plusieurs
bases, un arrêt du serveur affecterait toutes ces bases. Le projet Compose
constitue ici l'unité d'exploitation de chaque instance.

Cette organisation prépare aussi deux évolutions :

- Choisir des extensions par instance, par exemple une image intégrant
  [pgvector](https://github.com/pgvector/pgvector) pour une application qui en a
  besoin. Les fichiers de l'extension doivent être présents dans l'image, puis
  l'extension activée dans les bases concernées. Les autres instances peuvent
  conserver leur image et leur configuration.
- Ajouter un conteneur [postgres_exporter](https://github.com/prometheus-community/postgres_exporter)
  au projet Compose de chaque instance pour exposer ses métriques à Prometheus.
  Les cibles de collecte peuvent ainsi être identifiées par instance et
  application ; certaines métriques permettent aussi un suivi par base selon
  les collecteurs activés et les permissions SQL.

Ces évolutions sont suivies dans [TODO.md](../../TODO.md). La v1 utilise une
image officielle PostgreSQL 17 sur Alpine Linux 3.24 commune à toutes les instances, épinglée par version,
variante et digest dans [dependencies.json](../../dependencies.json), et ne déploie ni pgvector,
ni exporter, ni Prometheus.

## Conséquences

Les instances disposent de processus et de volumes distincts, mais partagent
CPU, RAM, disque, noyau invité et démon Docker. Aucune limite de ressources par
instance n'est définie. Cette séparation ne constitue pas une garantie d'isolation
pour des utilisateurs hostiles. La perte de la VM affecte toutes les bases.
L'indépendance concerne les opérations sur chaque instance : un redémarrage
de la VM, un arrêt de Docker ou une saturation des ressources partagées peut
toujours affecter toutes les applications. Plusieurs bases créées dans une
même instance resteraient également liées au cycle de vie de ce serveur.

Retirer une entrée du YAML ne supprime rien : le projet évite une destruction
implicite. Une mise à jour de l'image demande une modification volontaire du
digest et une validation après sauvegarde. Les ports nécessitent
un filtrage réseau extérieur au projet. Les sauvegardes et la HA sont hors v1.

## Réexamen

Revoir ce choix si la densité d'instances, les contraintes de sécurité ou la
disponibilité exigent des VM distinctes, un serveur mutualisé ou un orchestrateur.
Une migration majeure PostgreSQL doit inclure une procédure pour les données.

## Références

- [Image officielle PostgreSQL](https://hub.docker.com/_/postgres).
- [pgvector : installation et activation de l'extension](https://github.com/pgvector/pgvector).
- [postgres_exporter : métriques PostgreSQL pour Prometheus](https://github.com/prometheus-community/postgres_exporter).
- Code : [compose.yml.j2](../../ansible/templates/compose.yml.j2), [docker.yml](../../ansible/tasks/docker.yml).
- [Effet des changements](../configuration.md#effet-des-changements).

[Index des ADR](README.md)
