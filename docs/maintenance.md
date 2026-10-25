# Maintenance et vérifications

[Documentation](README.md)

## State local

OpenTofu conserve le suivi des ressources dans `terraform/terraform.tfstate`,
avec une éventuelle sauvegarde `terraform/terraform.tfstate.backup`. Ces fichiers
sont locaux et ignorés par Git : les protéger et les sauvegarder séparément.
Le state ne remplace pas une sauvegarde des données PostgreSQL.
`make clear` le déplace dans une archive locale restaurable ; ne pas supprimer
cette archive tant que le suivi de la VM est nécessaire.

Supprimer le state ne supprime pas les ressources sur Proxmox. OpenTofu perd
alors leur suivi. Si une VM existe déjà, restaurer un state valide ou préparer
un import explicite avant tout nouvel `apply`. Le projet ne réimporte
automatiquement ni la VM ni une image présente sans suivi.

Après un déplacement du projet ou une restauration, conserver les fichiers de
state avec la configuration dans `terraform/` et examiner le plan avant toute
application.

## Fichiers locaux et générés

| Chemin | Rôle et précautions |
| --- | --- |
| `terraform/terraform.tfvars`, `databases.yml` | Configurations locales ; conserver leurs valeurs et permissions `0600` |
| `terraform/terraform.tfstate*` | Suivi des ressources ; ne pas supprimer pour résoudre une erreur de déploiement |
| `terraform/.terraform/` | Cache et métadonnées d'initialisation ; recréés par `init` |
| `terraform/.terraform.lock.hcl` | Verrou du provider à versionner et conserver lors d'un nettoyage |
| `mise.lock`, `.mise/locks/` | Verrou des outils et graphes Python à versionner ensemble ; conservés par le nettoyage |
| `dependencies.json` | Références et empreintes des images et du bootstrap mise |
| `inventory.json` | Inventaire généré à la racine depuis les sorties OpenTofu |
| `.ansible/` | Fichiers temporaires, cache du lint et connexions SSH Ansible |
| `tmp/` | Archives privées créées par `clear`, avec leur manifeste de restauration |
| `.project.lock` | Verrou des commandes Make ; conservé pendant le nettoyage |
| `.reports/` | Rapports des scanners et de la CI, ignorés par Git |
| `.ruff_cache/` | Cache du lint Python |
| `**/__pycache__/` | Cache Python recréé lors de l'exécution des scripts et tests |

Après suppression du cache OpenTofu, `mise exec -- make init` réinstalle le
provider selon le verrou. `init` utilise `-lockfile=readonly` : il n'altère pas le verrou versionné.
Une mise à jour volontaire du provider doit utiliser `tofu init -upgrade`, puis
versionner le verrou après revue et validation.

## Nettoyage et restauration

Depuis la racine du projet :

```sh
make clear
make restore
make restore ARCHIVE=archive-identifiant-affiché
make clear-tmp
```

`clear` déplace les fichiers générés dans un dossier unique sous **`./tmp/` du
projet**, pas dans `/tmp` système. Il archive le cache `.terraform/`, le state et
sa sauvegarde, l'inventaire, `.ansible/`, `.ruff_cache/`, les caches Python, les
plans et les journaux de crash présents à la racine ou dans `terraform/`.
Il conserve `databases.yml`, `terraform.tfvars`, les exemples, le code, le verrou
du provider et les rapports `.reports/`.

Le dossier d'archive est privé (`0700`) et les fichiers déplacés directement
sont protégés (`0600`). Un manifeste enregistre les chemins d'origine. Les liens
symboliques sont refusés, y compris dans les caches : si un cache OpenTofu
partagé utilise des liens, cette commande refuse le nettoyage plutôt que de
suivre ces liens. Un verrou OpenTofu présent bloque aussi `clear`.

`restore` sans argument liste les archives. Avec `ARCHIVE=<identifiant>`, il
restaure les chemins à leur emplacement d'origine et retire l'archive restaurée.
Un conflit bloque la restauration avant tout déplacement : déplacer manuellement
le fichier en conflit après l'avoir examiné. Une opération interrompue peut être
relancée ; un fichier absent à la fois du projet et de l'archive bloque la restauration.

Tant qu'un state reste archivé, `check`, `security`, `init`, `prepare-image`, `plan`, `apply`,
`inventory`, `configure`, `deploy` et `status` refusent de commencer. Après
restauration, lancer `make init` puis examiner le plan avant toute application.
Le verrou `.project.lock` empêche les commandes Make concurrentes, y compris
pendant le nettoyage. Il est normal que ce fichier reste présent après la commande :
le verrou est libéré automatiquement à la fermeture du processus.

`clear-tmp` supprime uniquement les archives locales et refuse de perdre un
state non restauré. Pour abandonner **explicitement et définitivement** ce suivi :

```sh
make clear-tmp PURGE_STATE=1
```

Cette option ne détruit pas la VM ; elle supprime son suivi local archivé.
Les appels directs à OpenTofu ou Ansible contournent les protections Make.
`./tmp/` reste une commodité locale, pas une sauvegarde indépendante.

## Données sur la VM

Pour une instance d'identifiant `app`, les fichiers sont écrits dans
`/opt/postgres/app/` : `compose.yml` et `postgres_password`, accessibles à root.
Le projet Compose s'appelle `pg_app`, son volume `pg_app_data` et son réseau
`pg_app_network`.

Le volume est monté sur `/var/lib/postgresql/data`. Réappliquer Ansible ou
recréer le conteneur conserve les données du volume. Le volume reste néanmoins
sur le disque de la VM : supprimer ou remplacer celle-ci peut entraîner la perte
des données. Le projet ne met en place aucune sauvegarde automatique.

## Image Debian

Le nom et l'URL de l'image sont définis dans [terraform/image.tf](../terraform/image.tf).
La référence est lue depuis [dependencies.json](../dependencies.json) : build
daté, nom de fichier et SHA-512. Proxmox vérifie l'empreinte lors du téléchargement,
en plus de TLS. Un fichier déjà présent n'est pas automatiquement actualisé.

Avant `plan`, `apply` ou `deploy`, le script interroge l'API du stockage configuré :

1. Si le nom attendu est absent, OpenTofu téléchargera l'image lors de l'application.
2. S'il est présent et déjà suivi sous l'adresse `proxmox_download_file.debian`,
   l'image est réutilisée.
3. S'il est présent sans être suivi, le script bloque : le nom ne prouve pas son
   intégrité et aucune adoption automatique n'est réalisée.

Pour adopter volontairement une image existante, un administrateur doit vérifier
son origine et son SHA-512 sur le nœud, puis préparer un import manuel et relire
le plan. Une image déjà suivie n'est pas re-hachée périodiquement par le projet.
Aucun fichier existant n'est écrasé et une erreur API bloque la préparation.
Le téléchargement Debian vérifie TLS, même si la vérification du certificat
Proxmox a été désactivée.

Modifier le build peut remplacer l'image et éventuellement la VM qui en dépend :
examiner le plan et sauvegarder les données avant application. Le projet ne
migre pas les données PostgreSQL lors d'un remplacement de VM.

Un appel direct à OpenTofu contourne cette préparation. Pour conserver ce
comportement, utiliser les commandes Make ou mise du projet.

## Organisation Ansible

Les playbooks restent les points d'entrée utilisés par le Makefile :

| Fichier | Rôle |
| --- | --- |
| [deploy.yml](../ansible/deploy.yml) | Valide la configuration locale, attend la VM et orchestre le déploiement |
| [status.yml](../ansible/status.yml) | Consulte l'état des conteneurs PostgreSQL sur la VM |
| [check.yml](../ansible/check.yml) | Valide la configuration et le rendu Compose sur le PC |
| [tasks/validate.yml](../ansible/tasks/validate.yml) | Valide les champs, identifiants, ports et secrets sans afficher leurs valeurs |
| [tasks/docker.yml](../ansible/tasks/docker.yml) | Installe Docker et Compose, active Docker et contrôle les capacités Compose |
| [tasks/check-docker.yml](../ansible/tasks/check-docker.yml) | Vérifie le plugin Compose v2 ou supérieur et les options nécessaires, sans modifier Docker |
| [tasks/deploy-instance.yml](../ansible/tasks/deploy-instance.yml) | Prépare les fichiers d'une instance et démarre son projet Compose |
| [tasks/check-instance.yml](../ansible/tasks/check-instance.yml) | Contrôle le rendu Compose d'une instance dans un répertoire temporaire |
| [templates/compose.yml.j2](../ansible/templates/compose.yml.j2) | Modèle Compose utilisé par le déploiement et les contrôles locaux |

Les fichiers de `tasks/` sont inclus par les playbooks ; ils ne se lancent pas
seuls avec `ansible-playbook`. Le fichier [ansible.cfg](../ansible.cfg) reste à la
racine, avec les chemins de l'inventaire et des fichiers temporaires locaux.

## Scripts locaux

Les scripts Python utilisent uniquement la bibliothèque standard Python. Leurs
chemins sont calculés depuis leur emplacement, indépendamment du dossier courant.
Les commandes du projet continuent de se lancer depuis la racine.

| Fichier | Rôle |
| --- | --- |
| [scripts/local.py](../scripts/local.py) | Crée les configurations manquantes avec `setup` et écrit l'inventaire reçu sur l'entrée standard avec `inventory` |
| [scripts/prepare_image.py](../scripts/prepare_image.py) | Lit la configuration via OpenTofu, interroge Proxmox et refuse une image existante non suivie |
| [scripts/auth.sh](../scripts/auth.sh) | Demande le token et l'exporte dans le terminal Bash appelant |
| [scripts/maintenance.py](../scripts/maintenance.py) | Verrouille les commandes et gère archivage, restauration et purge |
| [scripts/test.py](../scripts/test.py) | Affiche les scénarios de tests et leur bilan |
| [scripts/security.py](../scripts/security.py) | Exécute Gitleaks et Trivy et conserve leurs rapports |
| [scripts/dependencies.py](../scripts/dependencies.py) | Contrôle les verrous, sources, empreintes déclarées et versions des outils |
| [scripts/check_docs.py](../scripts/check_docs.py) | Vérifie les liens et ancres Markdown locaux à la racine, dans `docs/` et `.github/`, sous-dossiers compris |

Chaque script Python possède un point d'entrée `main()` pour traiter les arguments et
les erreurs. Les opérations sur les fichiers, les appels HTTPS et les commandes
OpenTofu sont séparés en fonctions. Les messages d'erreur évitent d'afficher les
secrets, les réponses API et les sorties OpenTofu capturées.

Le [contrôle des liens documentaires](verification.md#liens-documentaires) détaille
l'utilisation de `check_docs.py`, son intégration à la CI et ses limites.

## Contrôles locaux

```sh
make check
```

Cette commande vérifie le format OpenTofu, initialise le provider, lance
`tofu validate`, exécute les tests OpenTofu avec provider simulé, vérifie Ansible,
Compose et les tests Python, puis lance les outils de lint et le contrôle documentaire.
Sans téléchargement du provider :

```sh
mise exec -- make check-local
```

Ces contrôles valident les entrées YAML, rendent le modèle Compose et lancent
les tests Python. Si Compose est disponible sur le PC, son parseur vérifie aussi
le rendu ; sinon, seul le contrôle YAML est effectué pour ce rendu et la limite
est signalée. Une configuration locale présente est validée : renseigner les
secrets avant de lancer ces commandes.

Les tests d'image utilisent des réponses API simulées. Les contrôles locaux ne
prouvent ni les permissions effectives sur Proxmox, ni la réussite du déploiement,
ni la persistance réelle des données. Un échec de démarrage du provider pendant
`tofu validate` est traité dans le [guide de dépannage](depannage.md#le-provider-ne-démarre-pas-pendant-la-validation).

## Organisation des tests

Les tests utilisent `unittest`, fourni avec Python, et sont répartis par responsabilité :

| Fichier | Couverture |
| --- | --- |
| [test_local.py](../tests/test_local.py) | Conservation des configurations, permissions et remplacement de l'inventaire |
| [test_prepare_image.py](../tests/test_prepare_image.py) | Réutilisation d'image suivie, refus d'adoption automatique, erreurs API et refus HTTP/redirections |
| [test_dependencies.py](../tests/test_dependencies.py) | Refus des images variables, verrous périmés, graphes absents et actions GitHub non épinglées |
| [test_docker.py](../tests/test_docker.py) | Compatibilité Compose : versions et options requises, via Ansible et une CLI simulée sans conteneur |
| [test_validation.py](../tests/test_validation.py) | Scénarios individuels de configuration et diagnostics Ansible sans exposition des secrets |
| [test_auth.py](../tests/test_auth.py) | Export Bash, erreurs, traçage et saisie masquée avec pseudo-terminal |
| [test_maintenance.py](../tests/test_maintenance.py) | Archivage, restauration, conflits, interruptions, protections et verrou |
| [test_security.py](../tests/test_security.py) | Orchestration des scanners et détection d'un secret factice archivé dans l'historique |
| [variables.tftest.hcl](../terraform/tests/variables.tftest.hcl) | Contraintes des variables et inventaire, avec provider simulé |

Pour lancer uniquement la suite automatisée depuis la racine :

```sh
make test
```

Les fichiers de test sont créés dans des répertoires temporaires. Les appels API
et OpenTofu des tests d'image sont simulés ; aucun token réel ni accès Proxmox
n'est nécessaire. Les tests de validation lancent réellement Ansible sur
`localhost`, uniquement pour exécuter les tâches de validation.

## Mise à jour des dépendances

Les versions changent par revue du dépôt, pas pendant l'installation en CI.
Depuis un poste disposant du réseau et de la version minimale de mise :

1. Modifier les versions exactes souhaitées dans `mise.toml` ou les références
   et empreintes dans `dependencies.json`, après examen des sources officielles.
2. Régénérer les métadonnées des outils avec `mise lock --platform linux-x64`.
   Pour actualiser aussi les transitives d'un outil Python inchangé, utiliser
   `mise lock --bump ansible pypi:ansible-lint --platform linux-x64`.
   Chaque projet sous `.mise/locks/` doit cibler `requires-python = "==3.14.*"`
   dans son `pyproject.toml` et son `uv.lock`, conformément au Python du dépôt.
   Après création ou renouvellement d'un graphe, ajuster cette contrainte dans
   le `pyproject.toml`, puis lancer `uv lock --project <répertoire-du-graphe>
   --default-index https://pypi.org/simple/ --exclude-newer <date-du-verrou>`.
   Reprendre la date `options.exclude-newer` du verrou pour conserver sa limite
   de résolution. Terminer par `mise lock ansible pypi:ansible-lint` pour
   enregistrer les nouvelles empreintes. Lors d'un changement de version mineure
   de Python, aligner également les contraintes des graphes et la cible Ruff.
3. Conserver ensemble `mise.lock` et tous les fichiers qu'il référence sous
   `.mise/locks/`. Examiner leurs sources, versions, empreintes et changements
   de provenance. `mise lock --upgrade` sert à changer de format du verrou.
4. Installer avec `mise install --locked`, puis exécuter `make check` et
   `make security`. Les alertes de vulnérabilités ne sont pas automatiquement
   acceptées, même si elles proviennent d'un outil ou d'une image officielle.

Pour un changement du provider, modifier `terraform/versions.tf`, puis lancer
`mise exec -- tofu -chdir=terraform init -upgrade` et examiner le verrou généré.
L'installation habituelle reste en `-lockfile=readonly`.

Pour Debian, récupérer le SHA-512 du fichier daté depuis le répertoire officiel
du build et vérifier aussi la signature du manifeste lorsque possible. Pour
PostgreSQL, relever le digest du manifeste du registre officiel pour le tag et
la variante choisis, puis scanner ce digest. Valider les locales, collations et
extensions attendues sur PostgreSQL Alpine, ainsi que la restauration des données.

Si la version de mise utilisée en CI change, modifier à la fois les workflows
et `dependencies.json`, avec le SHA-256 du binaire Linux x64 publié pour cette
release. Le contrôle des dépendances détecte une désynchronisation.

Les paquets APT de la VM restent issus des dépôts signés Debian et ne sont pas
gelés par ce verrou : les correctifs du système invité doivent être gérés et
testés séparément. Aucun `apt-mark hold` ni snapshot APT figé n'est imposé.

## Vérification sur un environnement de test

Le parcours suivant complète les contrôles locaux ; l'exécuter sur une instance
de test disposant d'une sauvegarde adaptée :

1. Déployer la VM, puis se connecter avec `psql`.
2. Créer une table de test et y écrire une ligne.
3. Ajouter une deuxième instance sur un autre port, puis lancer `configure`.
4. Réappliquer la configuration et vérifier que la ligne existe toujours.
5. Sur la VM, recréer le conteneur de test et vérifier à nouveau la ligne :

   ```sh
   sudo docker compose -f /opt/postgres/app/compose.yml up -d --force-recreate --wait
   ```

6. Retirer l'entrée de test du YAML, relancer `configure`, puis vérifier avec
   `status` que son ancien conteneur est toujours présent.

Adapter `app` à l'identifiant de test. Ces étapes décrivent une recette à réaliser ;
elles ne constituent pas un compte rendu de validation sur Proxmox.
