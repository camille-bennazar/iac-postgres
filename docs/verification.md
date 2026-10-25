# Vérification et intégration continue

[Documentation](README.md) · [Maintenance](maintenance.md)

## Versions des outils

Les versions des outils sont épinglées dans [mise.toml](../mise.toml).
L'[inventaire des dépendances](../DEPENDENCIES.md) détaille également les
composants déployés, leurs sources et les limites de reproductibilité.

| Outil | Version du projet | Source officielle / décision |
| --- | --- | --- |
| OpenTofu | 1.13.2 | [Release](https://github.com/opentofu/opentofu/releases/tag/v1.13.2) |
| Python | 3.14.8 | [Versions Python](https://www.python.org/downloads/) ; branche retenue pour Ansible et ansible-lint |
| uv | 0.13.5 | [Release](https://github.com/astral-sh/uv/releases/tag/0.13.5) ; installation des outils Python via mise |
| Ansible | 14.5.0 | [Paquet officiel](https://pypi.org/project/ansible/14.5.0/) |
| GNU Make | 4.4.1 | [Documentation GNU](https://www.gnu.org/software/make/manual/html_node/index.html) |
| Provider bpg/proxmox | 0.118.0 | [Release](https://github.com/bpg/terraform-provider-proxmox/releases/tag/v0.118.0) ; verrou versionné |
| Ruff | 0.17.1 | [Release stable](https://github.com/astral-sh/ruff/releases/tag/0.17.1) |
| ansible-lint | 26.10.1 | [Paquet officiel](https://pypi.org/project/ansible-lint/26.10.1/) |
| ShellCheck | 0.11.0 | [Release stable](https://github.com/koalaman/shellcheck/releases/tag/v0.11.0) |
| actionlint | 1.7.12 | [Release stable](https://github.com/rhysd/actionlint/releases/tag/v1.7.12) |
| Gitleaks | 8.30.1 | [Release stable](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1) |
| Trivy | 0.76.1 | [Release stable](https://github.com/aquasecurity/trivy/releases/tag/v0.76.1) |

La CI installe mise 2026.10.15 et vérifie le SHA-256 de son binaire Linux x64.
Le poste doit utiliser mise 2026.10.9 au minimum. Les versions et sources des
11 outils sont fixées dans [mise.lock](../mise.lock), avec les URL, empreintes
et métadonnées de provenance disponibles selon le backend. Les deux graphes
Python sous `.mise/locks/` fixent aussi les transitives et les empreintes des
wheels. Les dépendances Conda de Make sont incluses dans le verrou.

`mise install` applique le mode strict défini par `tool_config.locked = true`
pour ce projet. La CI utilise explicitement `--locked`. Un verrou absent ou
incomplet fait échouer l'installation ; il n'est pas régénéré en CI.
Ansible et ansible-lint conservent des environnements isolés, installés par uv.
Le verrou couvre actuellement Linux x64 ; une autre plateforme nécessite une
extension explicite et testée du verrou.

[dependencies.json](../dependencies.json) fixe l'image PostgreSQL par version,
variante et digest, l'image cloud Debian par build daté et SHA-512, et le binaire
mise utilisé en CI par version et SHA-256. Ansible et OpenTofu lisent directement
ce fichier pour leurs images. Les changements d'images sont volontaires ; ils
nécessitent une sauvegarde et la revue du plan, notamment si l'image de démarrage
entraîne un remplacement de VM. Voir la [maintenance](maintenance.md#mise-à-jour-des-dépendances).

Un SHA vérifie l'identité des octets attendus, pas l'absence de vulnérabilités.
Les signatures et attestations dépendent des publications et des backends ;
leur vérification ne couvre pas uniformément tous les outils.

## Contrôles locaux

| Commande | Contrôles |
| --- | --- |
| `make check-deps` | Politique d'épinglage, présence des verrous et graphes, sources autorisées, références CI et versions réellement exécutées |
| `make test` | Tests Python, scénarios Ansible locaux, authentification Bash et maintenance sur fichiers factices |
| `make check-local` | Syntaxe Ansible, validation YAML, rendu Compose, parseur Compose si disponible, puis tests Python |
| `make lint` | Ruff, ansible-lint, ShellCheck, actionlint, destinations et ancres Markdown locales |
| `make check` | Format et validation OpenTofu, tests avec provider simulé, contrôles locaux et lint |
| `make security` | Dépendances, initialisation du provider verrouillé, Gitleaks et scans Trivy des configurations, graphes Python, image PostgreSQL et dépendances Go embarquées |

Les scénarios Python sont affichés individuellement avec un bilan de réussites,
échecs et contrôles ignorés. Ils utilisent des secrets factices. Les tests de
nettoyage ne touchent pas aux fichiers de configuration ou au state du projet.

Une configuration `databases.yml` locale est contrôlée si elle existe. Après
`setup`, il faut donc remplacer les mots de passe d'exemple. Une copie propre
sans configuration personnelle permet de vérifier uniquement le code et les jeux
de données de test.

Gitleaks masque les secrets dans les journaux et rapports. Le scan local ignore
les configurations privées usuelles (`databases.yml`, fichiers `.tfvars`, `.env`),
les states, plans, archives et caches. Les fichiers d'exemple restent scannés.
Dans un dépôt Git, un scan strict contrôle aussi les changements préparés avec
`git add`, y compris un fichier privé ajouté avec `git add -f`, avant le premier commit.
Le scan d'historique n'exclut pas ces fichiers non plus, pour détecter
un fichier sensible commité par erreur. Trivy bloque les
configurations classées `HIGH` ou `CRITICAL`. Les rapports JSON sont dans
`.reports/`, ignoré par Git. Une erreur du scanner fait échouer la commande ;
une impossibilité de télécharger les règles ne constitue pas un résultat propre.
Les scans de vulnérabilités analysent les deux graphes `uv.lock`, l'image
PostgreSQL épinglée pour Linux amd64, le provider sélectionné et les binaires
Go d'OpenTofu, actionlint, Gitleaks et Trivy. Les binaires utilisent le mode
`rootfs` de Trivy, qui analyse leurs métadonnées de compilation. Un scan qui
ne produit aucun paquet analysé est considéré comme un échec.

La commande locale stricte échoue pour les alertes HIGH/CRITICAL actives. La CI
utilise `make security SECURITY_FLAGS=--allow-known` : les risques documentés dans
[le registre d’acceptation](../.github/security-accepted.json) sont non bloquants,
uniquement pour leur rapport, SHA-256 du binaire, CVE, paquet et version exacts. Les autres alertes
restent bloquantes, même sans correctif disponible. Les [risques connus et leur analyse](securite.md)
distinguent les alertes actives des exceptions démontrées non applicables.
[.trivyignore.yaml](../.trivyignore.yaml) limite chaque exception à une CVE,
un chemin et un paquet, avec justification et expiration après 30 jours.
Le script active les exceptions `gosu` uniquement pour le digest exact de l'image
analysée. Pour un outil, il vérifie le nom et le SHA-256 de l'exécutable avant de
charger ses exceptions. Un changement d'image ou de binaire exige un réexamen
avant de modifier les empreintes auditées dans `scripts/security.py`. Les scans
Python et provider n'utilisent aucune exception.
Les scans de vulnérabilités chargent explicitement ce fichier et conservent les
exceptions via `--show-suppressed` dans `ExperimentalModifiedFindings`. Le bilan
`dependencies-summary.json` compte séparément les alertes HIGH/CRITICAL actives
et les exceptions (`suppressed`), les risques acceptés (`accepted`) et les alertes
bloquantes (`blocking`). Les risques acceptés restent dans les vulnérabilités du
rapport Trivy et génèrent des avertissements CI. Un secret, une configuration IaC
HIGH/CRITICAL ou une erreur de scan reste bloquant ; aucun `continue-on-error`
global ni exclusion automatique des alertes sans correctif n'est utilisé.
Un binaire d'outil absent fait échouer le contrôle. Les anciens rapports sont
supprimés avant chaque scan pour éviter de présenter un résultat périmé.

Ces contrôles ne constituent pas un audit exhaustif : la VM réellement déployée,
les composants non identifiables des binaires, les collections embarquées Ansible
et les dépendances natives du poste ne sont pas tous couverts. Les scans Go
ne prouvent pas que chaque fonction vulnérable est atteignable. Les bases de
vulnérabilités et règles restent actualisées ; elles ne sont pas figées avec le code.

## Politique de dépendances

[scripts/dependencies.py](../scripts/dependencies.py) contrôle les versions
exactes, les entrées du verrou Linux x64, les graphes Python, les empreintes
déclarées, les sources de téléchargement autorisées, la cible Python de Ruff,
l'alignement des graphes Python sur la version mineure du projet, le verrou du provider et
les références d'images et de CI. La validation cryptographique des artefacts
et graphes est réalisée par mise et OpenTofu lors de l'installation.

La CI exécute ce contrôle statique avec le Python du runner avant l'installation
des outils. `make check-deps` ajoute la vérification des versions des exécutables
sur le PATH ; utiliser `mise exec -- make check-deps`. Ce contrôle fait partie
de `make check` et de `make security`.

## Liens documentaires

Le script [scripts/check_docs.py](../scripts/check_docs.py) détecte les liens
locaux cassés et les références à des sections absentes dans la documentation.
Il parcourt les fichiers Markdown à la racine du dépôt, ainsi que tous ceux de
`docs/` et `.github/`, sous-dossiers compris. Les ADR sont donc contrôlés aussi.

Pour chaque lien Markdown en ligne contenant un chemin et une éventuelle ancre, il
vérifie que le fichier cible existe dans le dépôt et, si une ancre vers un fichier
Markdown est précisée, qu'elle correspond à un titre. Les ancres sont calculées
à partir des titres, avec un suffixe pour les titres répétés.

```sh
python3 scripts/check_docs.py
```

Ce contrôle utilise uniquement la bibliothèque standard Python et ne demande
aucun accès réseau. Il est inclus dans `make lint`,
`make check` et le workflow CI. Une erreur affiche le document concerné et
la destination ou l'ancre absente, puis fait échouer la commande.

Le script reste un contrôle simple : il ne vérifie ni les URL externes, ni le
rendu Mermaid, ni toute la syntaxe Markdown. Les liens par référence et les
ancres HTML personnalisées ne sont pas pris en charge ; le calcul des ancres
ne remplace pas un moteur de rendu Markdown complet.

## CI GitHub

Les workflows s'exécutent sur GitHub hébergé avec Ubuntu 24.04 :

- **CI** : push, pull request et lancement manuel ; exécute `make check` sur une
  copie propre, sans créer les fichiers privés.
- **Sécurité** : mêmes événements et chaque jour à 06:23 UTC ; exécute
  `make security SECURITY_FLAGS=--allow-known` avec l’historique Git complet.
  Le cron et le lancement manuel sur la branche par défaut vérifient aussi les
  correctifs officiels et peuvent notifier Discord.
- Les actions sont épinglées par SHA et les droits du token GitHub sont limités
  à la lecture du contenu. Les identifiants de checkout ne sont pas conservés.
- Les bilans apparaissent dans le résumé GitHub. Les journaux de qualité et
  rapports de sécurité sont conservés sept jours dans les artifacts.
- Gitleaks est utilisé en CLI. Aucun secret Proxmox n'est nécessaire.
- Dependabot propose chaque semaine les mises à jour des actions GitHub.
  Les mises à jour proposées restent soumises à revue ; aucun auto-merge n’est configuré.
  Les versions des outils et du provider restent à mettre à jour explicitement.
- Le bootstrap mise est épinglé par SHA-256 et les outils sont installés depuis
  leurs verrous, après validation de la politique de dépendances.

Les workflows exécutent les contrôles sans déploiement automatique. Les règles
de protection de branche et les contrôles obligatoires avant fusion se configurent
dans les paramètres GitHub du dépôt.

## Notifications Discord des correctifs

Dans les paramètres du dépôt GitHub, ouvrir **Settings → Secrets and variables →
Actions → New repository secret**, puis créer **`DISCORD_WEBHOOK_URL`** avec l'URL
d'un webhook entrant Discord. Ne pas la mettre dans les fichiers, commandes
commitées ou logs. Aucun bot Discord ni token personnel GitHub n'est nécessaire.

Le workflow **Sécurité** s'exécute chaque jour à **06:23 UTC** (07:23 à Paris en
hiver, 08:23 en été). Les horaires GitHub peuvent être retardés. Le cron utilise
la branche par défaut ; après un fork, activer Actions. GitHub peut désactiver
les planifications d'un dépôt public après 60 jours sans activité.
Pour vérifier la configuration, lancer manuellement ce workflow depuis cette
branche. Une veille réussie envoie soit les nouvelles versions stables ou les correctifs confirmés, soit
un message de confirmation indiquant qu’aucune nouveauté n’est à notifier.
Ce message permet aussi de tester le webhook sans attendre un correctif.

La veille `python3 scripts/watch_patches.py check` :

1. Lit les rapports fraîchement produits et recherche les nouvelles releases
   stables du provider Proxmox et d’OpenTofu, même sans CVE active dans leurs
   versions épinglées. Gitleaks reste suivi pour les correctifs des CVE actives.
2. Consulte la release marquée stable la plus récente via l’API GitHub
   `releases/latest`, puis vérifie son tag sémantique et refuse explicitement les
   brouillons et préversions. Une version déjà épinglée n’est pas
   téléchargée ; une release majeure peut être signalée, sans installation automatique.
3. Vérifie l'origine de l'asset et son SHA-256 publié par l'API GitHub, extrait
   uniquement le binaire Linux amd64, puis lance Trivy sans exclusions, à toutes
   les sévérités : une simple baisse de gravité ne vaut pas correction. Le binaire
   téléchargé n'est jamais exécuté et les fichiers du projet ne sont pas modifiés.
4. Produit `.reports/patch-watch.json` et les scans candidats. Une nouvelle version
   stable du provider ou d’OpenTofu déclenche une alerte de disponibilité. Seules
   les CVE suivies qui ne sont plus détectées sont annoncées comme corrections ;
   une version et ses corrections sont regroupées dans un seul message.

`python3 scripts/watch_patches.py notify` transmet ensuite le composant, la version
candidate, les CVE concernées, le nombre d’autres CVE détectées et le lien officiel.
Sans nouvelle alerte à envoyer, il confirme la réussite de la veille, même si une
version ou un correctif a déjà été signalé auparavant. Chaque message comporte le lien vers
l’exécution GitHub lorsqu’il est lancé par le workflow.
Le secret Discord est disponible uniquement dans cette étape, sur la branche par
défaut lors du cron ou d'un lancement manuel ; jamais dans une pull request.
Les mentions Discord sont désactivées. Le token GitHub fourni à la lecture des
releases garde uniquement `contents: read`.

Les alertes de version ou de correction réussies sont mémorisées dans un cache GitHub Actions.
Les confirmations sans nouveauté sont envoyées à chaque veille réussie
et ne sont pas mises en cache. Un échec
Discord n'est pas mémorisé et sera réessayé au prochain passage. Le cache peut être
évincé par GitHub : une notification peut alors être répétée. Sans webhook, le
workflow affiche un avertissement indiquant que le résultat n’a pas été envoyé,
conserve le rapport et ne marque pas le message comme envoyé.

La veille reste exécutée même si le scan sécurité a trouvé une nouvelle alerte.
Une erreur de téléchargement, d'empreinte ou de scan est visible comme échec de
veille ; elle ne produit ni notification de correction ni confirmation de réussite. Les mises à jour des
versions, verrous, exceptions et acceptations restent manuelles et doivent être
suivies de `make check` et des scans de sécurité.

## Limites et recette Proxmox

Les contrôles locaux et la CI ne prouvent pas les ACL réelles du token, la
connectivité, le bon démarrage de cloud-init ou la persistance des données.
La [recette sur environnement de test](maintenance.md#vérification-sur-un-environnement-de-test)
reste nécessaire avant de confier des données utiles au déploiement.

Le projet reste adapté à un homelab avec une seule VM. Il n'ajoute ni sauvegarde
automatique, ni haute disponibilité, ni TLS PostgreSQL. Les archives `./tmp/`
facilitent le nettoyage mais ne remplacent pas une sauvegarde du state et des bases.
