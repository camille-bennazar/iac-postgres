# Travaux à suivre

Cette liste recense les évolutions envisagées après la v1. Une case ouverte
décrit un travail restant, pas une fonctionnalité disponible. Les choix actuels
sont expliqués dans les [ADR](docs/adr/README.md).

## Priorité suivante : protection des données

- [ ] Automatiser des sauvegardes PostgreSQL hors de la VM, avec rétention et test de restauration documenté.
- [ ] Documenter une procédure de reprise complète : state, configuration, secrets et données SQL.
- [ ] Définir une procédure de rotation des mots de passe sur des volumes déjà initialisés.
- [ ] Provisionner un utilisateur dédié par application, distinct du superutilisateur initial, avec permissions fines sur la base, les schémas, tables et séquences et privilèges par défaut pour les futurs objets, selon l'[ADR 0006](docs/adr/0006-secrets-et-initialisation.md).
- [ ] Prévoir l'application de ces droits sur les volumes déjà initialisés, séparer les droits de migration et d'exécution selon les besoins et tester les accès autorisés comme les accès refusés.
- [ ] Ajouter une procédure explicite de retrait d'instance, avec sauvegarde et confirmation avant suppression du volume.

## Reproductibilité et maintenance

- [ ] Ajouter un contrôle périodique d'intégrité des images Debian déjà suivies sur Proxmox ; le téléchargement vérifie le SHA-512, mais les fichiers existants ne sont pas re-hachés automatiquement.
- [ ] Suivre et traiter les alertes HIGH/CRITICAL des dépendances embarquées dans les outils et les images officielles ; documenter l'exploitabilité lorsqu'une mise à jour amont ne suffit pas.
- [ ] Produire un inventaire ou SBOM des dépendances transitives à partir des environnements Python, des paquets Debian et des images réellement installés.
- [ ] Automatiser les propositions de mises à jour des verrous mise, du provider, de Debian et du digest PostgreSQL ; Dependabot couvre actuellement les actions GitHub.
- [ ] Générer ou contrôler en CI les tableaux de versions de `DEPENDENCIES.md` depuis les versions et verrous déclarés ; conserver une revue humaine des explications, sources et limites.

## Validation des entrées Proxmox

- [ ] Renforcer les contraintes de syntaxe et de longueur des noms de nœud, de VM et des identifiants des deux stockages à partir de l'API Proxmox ciblée et des contraintes des backends ; distinguer les limites officielles des conventions du projet. `disk_storage` désigne un stockage, pas un nom de disque.
- [ ] Définir des plafonds documentés pour les CPU, la RAM et le disque afin de refuser des valeurs manifestement excessives, avec tests des bornes ; les plafonds statiques ne remplacent pas la vérification des ressources disponibles sur l'hôte.
- [ ] Évaluer une règle de RAM par multiples de 1024 Mio pour standardiser les allocations ; la présenter comme un choix du projet, Proxmox acceptant aussi d'autres allocations entières.

## Maintenabilité des contrôles et des tests

- [ ] Simplifier la validation des instances avec `ansible.builtin.assert`, en acceptant l'arrêt à la première erreur ; conserver les diagnostics de champs sans valeurs sensibles et les tests de non-divulgation, y compris pour les boucles et exceptions.
- [ ] Rédiger un ADR comparant les commandes Compose actuelles au module `community.docker.docker_compose_v2` : idempotence, diagnostics, secrets, versions du plugin et dépendances de collection à verrouiller.
- [ ] Mettre en cache les contenus ou ancres Markdown pendant une exécution du contrôleur documentaire afin d'éviter de relire et analyser un même fichier pour plusieurs liens.
- [ ] Étendre la couverture des liens et ancres du contrôleur documentaire avec des cas de test représentatifs avant de modifier les expressions régulières.
- [ ] Rédiger un ADR sur l'intérêt d'un parseur Markdown ou d'un AST si le périmètre dépasse les contrôles simples actuels ; comparer couverture, coût et dépendances.
- [ ] Étudier la portabilité de `scripts/dependencies.py` et du poste de contrôle vers macOS et Windows avec WSL : verrous par plateforme, exécutables, chemins, permissions et verrouillage des commandes. Ansible ne prend pas en charge Windows natif comme poste de contrôle.
- [ ] Répartir les tests de sécurité et de veille dans des classes par responsabilité, avec des fixtures partagées lorsque cela améliore la lisibilité, sans perdre les scénarios de panne et de protection des secrets.
- [ ] Évaluer Molecule pour des tests d'intégration Ansible sur un système représentatif ; conserver les tests unitaires rapides et les scénarios de validation et de non-divulgation des secrets.

## State distant auto-hébergé

- [ ] Évaluer Garage auto-hébergé avec le backend S3 d'OpenTofu pour partager le state entre postes et automatisations ; conserver le backend HTTP comme alternative.
- [ ] Tester sur la version de Garage retenue les écritures conditionnelles nécessaires au verrou S3 natif et deux exécutions concurrentes avant de valider cette solution.
- [ ] Vérifier le verrouillage concurrent, les droits d'accès, le chiffrement, les sauvegardes et la restauration du backend retenu, indépendamment de la VM PostgreSQL.
- [ ] Préparer et tester la migration du state local vers le backend distant, avec sauvegarde préalable et procédure de retour arrière.
- [ ] Adapter les protections des scripts de maintenance au backend distant, notamment le nettoyage et la restauration du state.

## Secrets auto-hébergés

- [ ] Évaluer OpenBao pour centraliser les secrets et fournir des accès limités aux opérateurs et à la CI, selon l'[ADR 0006](docs/adr/0006-secrets-et-initialisation.md).
- [ ] Définir l'intégration Ansible, l'authentification, les politiques d'accès et l'audit du coffre, sans exposition des secrets dans les journaux.
- [ ] Documenter et tester la sauvegarde, la restauration du coffre et la rotation des secrets dans les services concernés.

## Exploitation selon les besoins

- [ ] Installer et activer `qemu-guest-agent` via Ansible pour améliorer la gestion depuis Proxmox ; coordonner son activation côté VM avec le bootstrap OpenTofu, les délais d'attente et les droits minimaux, puis tester son fonctionnement.
- [ ] Ajouter des commandes ciblées pour arrêter, redémarrer et consulter une instance par son `id`, sans agir sur les autres projets Compose ni supprimer les volumes.
- [ ] Définir les accès réseau autorisés et documenter des règles de filtrage reproductibles.
- [ ] Ajouter TLS PostgreSQL si les usages réseau le nécessitent, avec gestion du renouvellement des certificats.
- [ ] Définir des limites de ressources par instance avant d'accueillir des charges plus importantes.
- [ ] Évaluer la haute disponibilité seulement si les objectifs de disponibilité dépassent ceux d'une VM de homelab.

## Provisionnement depuis l'IaC des applications

La [piste d'intégration](docs/integration-applications.md) décrit la création
de bases SQL sur des instances existantes depuis un projet IaC distinct.

- [ ] Valider et épingler le provider `cyrilgdn/postgresql` avec OpenTofu, puis proposer un module réutilisable de création de base, rôle applicatif et permissions pour les dépôts d'applications.
- [ ] Définir le contrat de connexion à une instance déjà provisionnée : hôte, port, base de maintenance, accès réseau et protection du transport SQL.
- [ ] Définir une propriété unique des ressources entre ce dépôt et les IaC applicatives, avec procédure de reprise d'une base initiale existante et règles de suppression protégeant les données.
- [ ] Intégrer le coffre OpenBao commun avec politiques par application et identifiants de provisionnement distincts des identifiants d'exécution ; attribuer à un seul composant la création et la rotation de chaque rôle et secret.
- [ ] Vérifier les secrets présents dans les plans et states des providers retenus et tester les mécanismes évitant leur persistance lorsqu'ils sont compatibles avec les versions choisies.
- [ ] Tester le parcours complet depuis un dépôt applicatif : création, réapplication sans changement, permissions minimales, rotation et suppression contrôlée, sans affecter les autres applications.

## Extensions par instance

- [ ] Permettre de choisir une image PostgreSQL validée par instance, avec versions épinglées et contrôle de compatibilité avec les volumes existants.
- [ ] Ajouter un profil pgvector : image contenant l'extension, activation dans les bases choisies et test fonctionnel.
- [ ] Définir le cycle de mise à jour des extensions et les procédures de sauvegarde et restauration associées, sans imposer ces extensions aux autres instances.

## Supervision Prometheus

- [ ] Ajouter en option un conteneur `postgres_exporter` par projet Compose, avec image épinglée, compte SQL dédié aux droits de supervision et secret distinct du compte applicatif.
- [ ] Configurer les cibles de collecte Prometheus, les accès réseau et les labels permettant d'identifier chaque instance et application.
- [ ] Définir les métriques attendues par instance et par base, puis vérifier les collecteurs et permissions nécessaires sur une instance de test.
- [ ] Prévoir des tableaux de bord et alertes pour la disponibilité, les connexions, l'espace disque et les sauvegardes, avec les sources de métriques complémentaires nécessaires.

[Présentation](README.md) · [Documentation](docs/README.md)
