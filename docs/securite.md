# Sécurité et risques connus

[Documentation](README.md) · [Vérifications](verification.md) · [Dépendances](../DEPENDENCIES.md)

## Politique

`make security` reste strict : toute alerte HIGH/CRITICAL active fait échouer
la commande. En CI, `make security SECURITY_FLAGS=--allow-known` autorise uniquement
les risques recensés dans [.github/security-accepted.json](../.github/security-accepted.json),
avec une correspondance exacte du rapport, du SHA-256 du binaire, de la CVE,
du paquet et de sa version.
Cette acceptation est une décision de maintien du pipeline pour le périmètre
homelab décrit ici ; elle ne constitue pas une preuve de non-applicabilité.

Les 26 détections connues, dont une CRITICAL, restent visibles dans les rapports,
le résumé GitHub et les avertissements CI. Elles ne sont pas ajoutées au fichier
d'exclusions Trivy. Une nouvelle alerte, un secret, une configuration IaC HIGH/CRITICAL,
un outil absent ou un scan incomplet reste bloquant. Une version exacte et son
empreinte garantissent l'artefact attendu, pas l'absence de vulnérabilités.

Les exceptions concernent uniquement des alertes démontrées non applicables au
binaire examiné. Elles ont un identifiant CVE, un chemin, un paquet,
une justification et une expiration dans [.trivyignore.yaml](../.trivyignore.yaml).
Trivy conserve les exceptions dans `ExperimentalModifiedFindings` des rapports
JSON et le bilan les compte séparément. Aucune option `--ignore-unfixed` n'est utilisée.

## Versions et correctifs

Vérification des distributions officielles le **22 octobre 2026** :

| Composant | Version examinée | Distribution officielle |
| --- | --- | --- |
| PostgreSQL | 17.11, Alpine 3.24, digest fixé dans `dependencies.json` | [Images officielles](https://github.com/docker-library/official-images/blob/master/library/postgres) |
| gosu dans cette image | 1.19, compilé avec Go 1.24.6 | [Release 1.19](https://github.com/tianon/gosu/releases/tag/1.19) |
| Provider Proxmox | 0.118.0, Go 1.26.9 | [Release 0.118.0](https://github.com/bpg/terraform-provider-proxmox/releases/tag/v0.118.0) |
| OpenTofu | 1.13.2 ; x/mod 0.39.0, x/net 0.57.0, gRPC 1.83.1 | [Release 1.13.2](https://github.com/opentofu/opentofu/releases/tag/v1.13.2) |
| actionlint | 1.7.12, Go 1.26.1 | [Release 1.7.12](https://github.com/rhysd/actionlint/releases/tag/v1.7.12) |
| Gitleaks | 8.30.1, Go 1.24.11 ; compress 1.17.11, x/crypto 0.35.0, x/text 0.22.0 | [Release 8.30.1](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1) |
| Trivy | 0.76.1, Go 1.27.3 | [Release 0.76.1](https://github.com/aquasecurity/trivy/releases/tag/v0.76.1) |

Ces versions sont les dernières releases stables des composants concernés à la
date de vérification. Des correctifs existent dans les bibliothèques listées
ci-dessous ; ils ne constituent pas encore une nouvelle distribution officielle
des outils qui les embarquent. Changer le Go installé sur le poste ne corrige pas
un binaire déjà compilé. Le projet utilise les artefacts officiels, sans build maison.

Les graphes Python et les paquets système de l'image Alpine ne présentent pas
d'alerte HIGH/CRITICAL dans les rapports examinés. Cela ne couvre ni les paquets
APT de la VM réellement déployée, ni tous les composants non reconnus par Trivy.

## Alertes actives

Analyse du **22 octobre 2026**, après examen des distributions officielles,
des avis amont, des sources des versions épinglées et des exécutables Linux amd64.
Le registre couvre chaque couple CVE/composant signalé : une même CVE peut être
non applicable à un outil et rester un risque actif accepté en CI dans un autre.

| Composant | HIGH actives | CRITICAL actives | Non applicables exclues |
| --- | --- | --- | --- |
| Provider Proxmox | 1 | 0 | 0 |
| OpenTofu | 1 | 0 | 3 |
| actionlint | 0 | 0 | 24 |
| Gitleaks | 23 | 1 | 15 |
| PostgreSQL / gosu | 0 | 0 | 26 |
| Python et Trivy | 0 | 0 | 0 |

**25 HIGH et 1 CRITICAL restent actives**, pour 24 CVE distinctes. Elles sont
acceptées en CI pour les versions et artefacts explicitement recensés ; le contrôle
local strict continue d’échouer.
Les 68 détections exclues ont une portée documentée ; elles ne sont pas des
correctifs. Aucun nouvel artefact officiel corrigé n'a été trouvé.
Les alertes restantes sont classées **incertaines** : les API vulnérables sont
présentes ou leur accessibilité n'est pas exclue, sans preuve d'exploitation dans
ce projet. Le contrôle TLS du provider est effectivement utilisé.

Le correctif indiqué est celui de la bibliothèque, pas une version disponible de
l'outil. Les codes CERT, RÉSEAU, etc. décrivent l'impact et les contrôles ci-dessous ;
les autres codes renvoient aux [preuves des exceptions](#exceptions-outils).

| CVE | Composant | État | Correctif bibliothèque | Preuve / contrôle |
| --- | --- | --- | --- | --- |
| [CVE-2026-111943](https://pkg.go.dev/vuln/GO-2026-6809) | Provider | Incertaine — acceptée en CI | 1.26.10, 1.27.3 | CERT |
| [CVE-2026-56864](https://pkg.go.dev/vuln/GO-2026-6180) | OpenTofu | Non applicable | 0.40.0 | T-SUMDB |
| [CVE-2026-56865](https://pkg.go.dev/vuln/GO-2026-6179) | OpenTofu | Non applicable | 0.40.0 | T-SUMDB |
| [CVE-2026-78669](https://pkg.go.dev/vuln/GO-2026-6611) | OpenTofu | Incertaine — acceptée en CI | 0.60.0 | RÉSEAU |
| [CVE-2026-84445](https://pkg.go.dev/vuln/GO-2026-6443) | OpenTofu | Non applicable | 1.82.2, 1.83.2, 1.84.0-dev.0.20260825144003-d5a41119e0e3, 1.85.0-dev.0.20260825072537-93e31b48545e | T-XDS |
| [CVE-2026-111943](https://pkg.go.dev/vuln/GO-2026-6809) | actionlint | Non applicable | 1.26.10, 1.27.3 | A-IMPORT |
| [CVE-2026-27145](https://pkg.go.dev/vuln/GO-2026-5037) | actionlint | Non applicable | 1.25.11, 1.26.4 | A-IMPORT |
| [CVE-2026-32280](https://pkg.go.dev/vuln/GO-2026-4947) | actionlint | Non applicable | 1.25.9, 1.26.2 | A-IMPORT |
| [CVE-2026-32281](https://pkg.go.dev/vuln/GO-2026-4946) | actionlint | Non applicable | 1.25.9, 1.26.2 | A-IMPORT |
| [CVE-2026-32283](https://pkg.go.dev/vuln/GO-2026-4870) | actionlint | Non applicable | 1.25.9, 1.26.2 | A-IMPORT |
| [CVE-2026-33810](https://pkg.go.dev/vuln/GO-2026-4866) | actionlint | Non applicable | 1.26.2 | A-IMPORT |
| [CVE-2026-33811](https://pkg.go.dev/vuln/GO-2026-4981) | actionlint | Non applicable | 1.25.10, 1.26.3 | A-IMPORT |
| [CVE-2026-33814](https://pkg.go.dev/vuln/GO-2026-4918) | actionlint | Non applicable | 1.25.10, 1.26.3 | A-IMPORT |
| [CVE-2026-33818](https://pkg.go.dev/vuln/GO-2026-5972) | actionlint | Non applicable | 1.25.13, 1.26.6, 1.27.0-rc.3 | A-IMPORT |
| [CVE-2026-39820](https://pkg.go.dev/vuln/GO-2026-4986) | actionlint | Non applicable | 1.25.10, 1.26.3 | A-IMPORT |
| [CVE-2026-39821](https://pkg.go.dev/vuln/GO-2026-5026) | actionlint | Non applicable | 1.25.13, 1.26.6, 1.27.0-rc.3 | A-IMPORT |
| [CVE-2026-39822](https://pkg.go.dev/vuln/GO-2026-4970) | actionlint | Non applicable | 1.25.12, 1.26.5, 1.27.0-rc.2 | ROOT |
| [CVE-2026-39836](https://pkg.go.dev/vuln/GO-2026-4971) | actionlint | Non applicable | 1.25.10, 1.26.3 | A-IMPORT |
| [CVE-2026-42499](https://pkg.go.dev/vuln/GO-2026-4977) | actionlint | Non applicable | 1.25.10, 1.26.3 | A-IMPORT |
| [CVE-2026-42504](https://pkg.go.dev/vuln/GO-2026-5038) | actionlint | Non applicable | 1.25.11, 1.26.4 | A-IMPORT |
| [CVE-2026-46600](https://pkg.go.dev/vuln/GO-2026-5942) | actionlint | Non applicable | 1.26.6, 1.27.0-rc.3 | A-IMPORT |
| [CVE-2026-56853](https://pkg.go.dev/vuln/GO-2026-6089) | actionlint | Non applicable | 1.25.13, 1.26.6, 1.27.0-rc.3 | A-IMPORT |
| [CVE-2026-56858](https://pkg.go.dev/vuln/GO-2026-6091) | actionlint | Non applicable | 1.25.13, 1.26.6, 1.27.0-rc.3 | A-IMPORT |
| [CVE-2026-56859](https://pkg.go.dev/vuln/GO-2026-6088) | actionlint | Non applicable | 1.25.13, 1.26.6, 1.27.0-rc.3 | A-IMPORT |
| [CVE-2026-56860](https://pkg.go.dev/vuln/GO-2026-6218) | actionlint | Non applicable | 1.25.13, 1.26.6, 1.27.0-rc.3 | A-URL |
| [CVE-2026-56862](https://pkg.go.dev/vuln/GO-2026-6090) | actionlint | Non applicable | 1.25.13, 1.26.6, 1.27.0-rc.3 | A-IMPORT |
| [CVE-2026-78667](https://pkg.go.dev/vuln/GO-2026-6609) | actionlint | Non applicable | 1.26.9, 1.27.2 | A-IMPORT |
| [CVE-2026-78669](https://pkg.go.dev/vuln/GO-2026-6611) | actionlint | Non applicable | 1.26.9, 1.27.2 | A-IMPORT |
| [CVE-2026-97031](https://pkg.go.dev/vuln/GO-2026-6607) | actionlint | Non applicable | 1.26.9, 1.27.2 | A-IMPORT |
| [CVE-2025-47913](https://pkg.go.dev/vuln/GO-2025-4116) | Gitleaks | Non applicable | 0.43.0 | G-SSH |
| [CVE-2025-61726](https://pkg.go.dev/vuln/GO-2026-4341) | Gitleaks | Incertaine — acceptée en CI | 1.24.12, 1.25.6 | RÉSEAU |
| [CVE-2025-68121](https://pkg.go.dev/vuln/GO-2026-4337) | Gitleaks | Incertaine — acceptée en CI | 1.24.13, 1.25.7, 1.26.0-rc.3 | CERT |
| [CVE-2026-111943](https://pkg.go.dev/vuln/GO-2026-6809) | Gitleaks | Incertaine — acceptée en CI | 1.26.10, 1.27.3 | CERT |
| [CVE-2026-25679](https://pkg.go.dev/vuln/GO-2026-4601) | Gitleaks | Incertaine — acceptée en CI | 1.25.8, 1.26.1 | RÉSEAU |
| [CVE-2026-27145](https://pkg.go.dev/vuln/GO-2026-5037) | Gitleaks | Incertaine — acceptée en CI | 1.25.11, 1.26.4 | CERT |
| [CVE-2026-32280](https://pkg.go.dev/vuln/GO-2026-4947) | Gitleaks | Incertaine — acceptée en CI | 1.25.9, 1.26.2 | CERT |
| [CVE-2026-32281](https://pkg.go.dev/vuln/GO-2026-4946) | Gitleaks | Incertaine — acceptée en CI | 1.25.9, 1.26.2 | CERT |
| [CVE-2026-32283](https://pkg.go.dev/vuln/GO-2026-4870) | Gitleaks | Incertaine — acceptée en CI | 1.25.9, 1.26.2 | RÉSEAU |
| [CVE-2026-33811](https://pkg.go.dev/vuln/GO-2026-4981) | Gitleaks | Incertaine — acceptée en CI | 1.25.10, 1.26.3 | RÉSEAU |
| [CVE-2026-33814](https://pkg.go.dev/vuln/GO-2026-4918) | Gitleaks | Incertaine — acceptée en CI | 1.25.10, 1.26.3 | RÉSEAU |
| [CVE-2026-33818](https://pkg.go.dev/vuln/GO-2026-5972) | Gitleaks | Incertaine — acceptée en CI | 1.25.13, 1.26.6, 1.27.0-rc.3 | PARSEUR |
| [CVE-2026-39820](https://pkg.go.dev/vuln/GO-2026-4986) | Gitleaks | Incertaine — acceptée en CI | 1.25.10, 1.26.3 | PARSEUR |
| [CVE-2026-39821](https://pkg.go.dev/vuln/GO-2026-5026) | Gitleaks | Incertaine — acceptée en CI | 1.25.13, 1.26.6, 1.27.0-rc.3 | RÉSEAU |
| [CVE-2026-39822](https://pkg.go.dev/vuln/GO-2026-4970) | Gitleaks | Non applicable | 1.25.12, 1.26.5, 1.27.0-rc.2 | ROOT |
| [CVE-2026-39828](https://pkg.go.dev/vuln/GO-2026-5014) | Gitleaks | Non applicable | 0.52.0 | G-SSH |
| [CVE-2026-39829](https://pkg.go.dev/vuln/GO-2026-5018) | Gitleaks | Non applicable | 0.52.0 | G-SSH |
| [CVE-2026-39830](https://pkg.go.dev/vuln/GO-2026-5017) | Gitleaks | Non applicable | 0.52.0 | G-SSH |
| [CVE-2026-39831](https://pkg.go.dev/vuln/GO-2026-5019) | Gitleaks | Non applicable | 0.52.0 | G-SSH |
| [CVE-2026-39832](https://pkg.go.dev/vuln/GO-2026-5006) | Gitleaks | Non applicable | 0.52.0 | G-SSH |
| [CVE-2026-39835](https://pkg.go.dev/vuln/GO-2026-5015) | Gitleaks | Non applicable | 0.52.0 | G-SSH |
| [CVE-2026-39836](https://pkg.go.dev/vuln/GO-2026-4971) | Gitleaks | Non applicable | 1.25.10, 1.26.3 | LINUX |
| [CVE-2026-42499](https://pkg.go.dev/vuln/GO-2026-4977) | Gitleaks | Incertaine — acceptée en CI | 1.25.10, 1.26.3 | PARSEUR |
| [CVE-2026-42504](https://pkg.go.dev/vuln/GO-2026-5038) | Gitleaks | Incertaine — acceptée en CI | 1.25.11, 1.26.4 | PARSEUR |
| [CVE-2026-42508](https://pkg.go.dev/vuln/GO-2026-5021) | Gitleaks | Non applicable | 0.52.0 | G-SSH |
| [CVE-2026-46595](https://pkg.go.dev/vuln/GO-2026-5023) | Gitleaks | Non applicable | 0.52.0 | G-SSH |
| [CVE-2026-46597](https://pkg.go.dev/vuln/GO-2026-5013) | Gitleaks | Non applicable | 0.52.0 | G-SSH |
| [CVE-2026-56851](https://pkg.go.dev/vuln/GO-2026-6629) | Gitleaks | Non applicable | 0.41.0 | G-PRECIS |
| [CVE-2026-56852](https://pkg.go.dev/vuln/GO-2026-5970) | Gitleaks | Incertaine — acceptée en CI | 0.39.0 | TEXTE |
| [CVE-2026-56853](https://pkg.go.dev/vuln/GO-2026-6089) | Gitleaks | Incertaine — acceptée en CI | 1.25.13, 1.26.6, 1.27.0-rc.3 | RÉSEAU |
| [CVE-2026-56854](https://pkg.go.dev/vuln/GO-2026-6303) | Gitleaks | Non applicable | 0.55.0 | G-SSH |
| [CVE-2026-56858](https://pkg.go.dev/vuln/GO-2026-6091) | Gitleaks | Incertaine — acceptée en CI | 1.25.13, 1.26.6, 1.27.0-rc.3 | PARSEUR |
| [CVE-2026-56859](https://pkg.go.dev/vuln/GO-2026-6088) | Gitleaks | Incertaine — acceptée en CI | 1.25.13, 1.26.6, 1.27.0-rc.3 | PARSEUR |
| [CVE-2026-56860](https://pkg.go.dev/vuln/GO-2026-6218) | Gitleaks | Incertaine — acceptée en CI | 1.25.13, 1.26.6, 1.27.0-rc.3 | RÉSEAU |
| [CVE-2026-56862](https://pkg.go.dev/vuln/GO-2026-6090) | Gitleaks | Incertaine — acceptée en CI | 1.25.13, 1.26.6, 1.27.0-rc.3 | RÉSEAU |
| [CVE-2026-63209](https://github.com/klauspost/compress/security/advisories/GHSA-259r-337f-4rfw) | Gitleaks | Non applicable | 1.18.7 | G-S2 |
| [CVE-2026-78667](https://pkg.go.dev/vuln/GO-2026-6609) | Gitleaks | Incertaine — acceptée en CI | 1.26.9, 1.27.2 | RÉSEAU |
| [CVE-2026-78669](https://pkg.go.dev/vuln/GO-2026-6611) | Gitleaks | Incertaine — acceptée en CI | 1.26.9, 1.27.2 | RÉSEAU |
| [CVE-2026-97031](https://pkg.go.dev/vuln/GO-2026-6607) | Gitleaks | Incertaine — acceptée en CI | 1.26.9, 1.27.2 | RÉSEAU |

Les impacts ci-dessous sont possibles si le chemin vulnérable reçoit l'entrée
nécessaire. La présence d'un symbole dans un binaire ne démontre pas cette
accessibilité ; en l'absence de preuve contraire, l'alerte reste active.

| Contrôle | Impact possible et vérifications à effectuer |
| --- | --- |
| CERT | Validation incorrecte de certificats ou épuisement de ressources. Vérifier les chemins TLS/X.509 réellement utilisés, la confiance des CA du poste et les certificats de Proxmox. Garder la vérification TLS active et suivre le correctif du provider. |
| RÉSEAU | Épuisement CPU/mémoire, blocage ou interprétation incorrecte d'une adresse. Vérifier si le client ou serveur HTTP/2, TLS, DNS ou URL concerné traite des entrées non fiables ; limiter les destinations réseau et exécuter les outils sans droits supplémentaires. |
| SSH | Contournement d'authentification/permissions ou déni de service dans la bibliothèque SSH. Vérifier si Gitleaks utilise effectivement ces fonctions dans les commandes `dir` et `git` retenues ; leur simple inclusion dans le binaire ne suffit pas à conclure. |
| ARCHIVE | Déni de service pendant la décompression. Vérifier le traitement des archives et dictionnaires fournis par un dépôt non fiable ; isoler les scans de contributions externes et limiter leur durée. |
| TEXTE | Panique ou consommation excessive de ressources sur certaines entrées Unicode. Vérifier les profils et décodeurs effectivement appelés par Gitleaks sur les fichiers examinés. |
| MODULE | Contournement des vérifications de transparence des modules Go. Vérifier si OpenTofu appelle les fonctions sumdb concernées ; ne pas confondre cette base Go avec le verrou et les signatures des providers OpenTofu. |
| GRPC | Arrêt d'un serveur gRPC par requête malformée. Vérifier la création d'un serveur xDS et son accessibilité dans les échanges locaux OpenTofu/provider avant de conclure à une exposition. |
| FICHIERS | Traversée de répertoires via les API `os.Root`. Vérifier les symboles et appels concernés, la plateforme et l'influence possible sur les liens symboliques. |
| PARSEUR | Déni de service ou, pour les templates HTML, sortie incorrectement échappée. Vérifier le parseur, la fonction et le contenu contrôlé par un tiers ; la présence d'une bibliothèque ne prouve pas que cet usage est exposé. |

Les limites de durée des jobs CI réduisent certains blocages, mais ne corrigent
pas ces vulnérabilités. Les scans de contributions externes n'utilisent aucun
secret Proxmox et le token GitHub n'a qu'un accès en lecture au contenu.

## Exceptions gosu

Les 26 alertes Go ci-dessous sont exclues **uniquement** pour
`usr/local/bin/gosu`, paquet `stdlib` de Go 1.24.6, jusqu'au **21 novembre 2026**.
Le script ne charge ces exceptions que pour le digest exact de l'image analysée
(`GOSU_AUDITED_IMAGE` dans `scripts/security.py`). Un autre digest utilise
`--ignorefile ""`. Les exclusions combinent CVE, chemin et PURL du paquet
avec sa version ; le digest borne aussi le contenu complet de l'image.
Les exceptions gosu ne s'appliquent pas aux autres exécutables.

Analyse le 22 octobre 2026 avec `govulncheck` 1.9.0, mode `binary`, niveau `symbol`,
base officielle Go datée du 21 octobre 2026. Le binaire est extrait de l'image
PostgreSQL épinglée, sans exécuter le conteneur. SHA-256 de gosu :
`52c8749d0142edd234e9d6bd5237dff2d81e71f43537e2f4f66f75dd4b243dd0`.
Chaque CVE est présente dans la base Go ; aucun de ses symboles affectés n'est
signalé dans ce binaire. Cette observation concorde avec le rôle local de gosu,
les [sources de la version 1.19](https://github.com/tianon/gosu/tree/1.19) et la
[politique de sécurité amont](https://github.com/tianon/gosu/blob/master/SECURITY.md).

Cette analyse ne dit pas que gosu est exempt de toute vulnérabilité. Elle porte
sur ces CVE et ce binaire précis. Le correctif Go indiqué n'est pas nécessaire
pour une fonction absente ; toute modification du binaire exige une nouvelle analyse.

| CVE non applicable à ce binaire | Versions Go corrigées selon le rapport |
| --- | --- |
| [CVE-2025-61726](https://pkg.go.dev/vuln/GO-2026-4341) | 1.24.12, 1.25.6 |
| [CVE-2025-61729](https://pkg.go.dev/vuln/GO-2025-4155) | 1.24.11, 1.25.5 |
| [CVE-2025-68121](https://pkg.go.dev/vuln/GO-2026-4337) | 1.24.13, 1.25.7, 1.26.0-rc.3 |
| [CVE-2026-111943](https://pkg.go.dev/vuln/GO-2026-6809) | 1.26.10, 1.27.3 |
| [CVE-2026-25679](https://pkg.go.dev/vuln/GO-2026-4601) | 1.25.8, 1.26.1 |
| [CVE-2026-27145](https://pkg.go.dev/vuln/GO-2026-5037) | 1.25.11, 1.26.4 |
| [CVE-2026-32280](https://pkg.go.dev/vuln/GO-2026-4947) | 1.25.9, 1.26.2 |
| [CVE-2026-32281](https://pkg.go.dev/vuln/GO-2026-4946) | 1.25.9, 1.26.2 |
| [CVE-2026-32283](https://pkg.go.dev/vuln/GO-2026-4870) | 1.25.9, 1.26.2 |
| [CVE-2026-33811](https://pkg.go.dev/vuln/GO-2026-4981) | 1.25.10, 1.26.3 |
| [CVE-2026-33814](https://pkg.go.dev/vuln/GO-2026-4918) | 1.25.10, 1.26.3 |
| [CVE-2026-33818](https://pkg.go.dev/vuln/GO-2026-5972) | 1.25.13, 1.26.6, 1.27.0-rc.3 |
| [CVE-2026-39820](https://pkg.go.dev/vuln/GO-2026-4986) | 1.25.10, 1.26.3 |
| [CVE-2026-39821](https://pkg.go.dev/vuln/GO-2026-5026) | 1.25.13, 1.26.6, 1.27.0-rc.3 |
| [CVE-2026-39822](https://pkg.go.dev/vuln/GO-2026-4970) | 1.25.12, 1.26.5, 1.27.0-rc.2 |
| [CVE-2026-39836](https://pkg.go.dev/vuln/GO-2026-4971) | 1.25.10, 1.26.3 |
| [CVE-2026-42499](https://pkg.go.dev/vuln/GO-2026-4977) | 1.25.10, 1.26.3 |
| [CVE-2026-42504](https://pkg.go.dev/vuln/GO-2026-5038) | 1.25.11, 1.26.4 |
| [CVE-2026-56853](https://pkg.go.dev/vuln/GO-2026-6089) | 1.25.13, 1.26.6, 1.27.0-rc.3 |
| [CVE-2026-56858](https://pkg.go.dev/vuln/GO-2026-6091) | 1.25.13, 1.26.6, 1.27.0-rc.3 |
| [CVE-2026-56859](https://pkg.go.dev/vuln/GO-2026-6088) | 1.25.13, 1.26.6, 1.27.0-rc.3 |
| [CVE-2026-56860](https://pkg.go.dev/vuln/GO-2026-6218) | 1.25.13, 1.26.6, 1.27.0-rc.3 |
| [CVE-2026-56862](https://pkg.go.dev/vuln/GO-2026-6090) | 1.25.13, 1.26.6, 1.27.0-rc.3 |
| [CVE-2026-78667](https://pkg.go.dev/vuln/GO-2026-6609) | 1.26.9, 1.27.2 |
| [CVE-2026-78669](https://pkg.go.dev/vuln/GO-2026-6611) | 1.26.9, 1.27.2 |
| [CVE-2026-97031](https://pkg.go.dev/vuln/GO-2026-6607) | 1.26.9, 1.27.2 |

Pour reproduire l'examen ponctuel avec un `govulncheck` vérifié, extraire le binaire
de l'image épinglée puis exécuter `govulncheck -mode=binary -json /chemin/vers/gosu`.
Vérifier à la fois la présence de l'avis CVE dans la base consultée et l'absence
des symboles affectés ; une base ancienne ou une analyse incomplète ne suffit pas.
Cet outil d'audit ponctuel n'est pas une dépendance nécessaire au déploiement ou à la CI.

### Autre alerte gosu à surveiller

[CVE-2026-61801 / GO-2026-6686](https://pkg.go.dev/vuln/GO-2026-6686) concerne
`github.com/moby/sys/user` 0.1.0 embarqué dans gosu. Le correctif est en 0.4.1 ;
la release officielle gosu 1.19 ne l'intègre pas. L'avis amont est de sévérité
modérée et cette alerte n'apparaît pas dans le scan Trivy limité aux HIGH/CRITICAL.
L'analyse binaire détecte des symboles affectés : **aucune exception n'est accordée**.

Une personne capable de fournir un fichier de comptes ou de groupes malveillant
pourrait provoquer une consommation excessive de mémoire au changement d'utilisateur.
Le projet n'importe pas ces fichiers depuis les applications : garder `/etc/passwd`
et `/etc/group` de l'image hors de leur contrôle, ne pas les monter depuis une
source non fiable et vérifier l'intégration de la bibliothèque corrigée dans une
prochaine image. Voir l'[avis officiel Moby](https://github.com/moby/sys/security/advisories/GHSA-mjcv-p78q-w5fw).

## Exceptions outils

Les **42 exceptions** d'outils expirent le **21 novembre 2026**. Le registre
ci-dessus indique chaque CVE et sa preuve ; aucune exception ne vise le provider.
Le script charge le fichier uniquement pour un scan `rootfs` d'un exécutable dont
le nom **et le SHA-256** correspondent à cette table. Un autre contenu ou un autre
nom réactive les alertes ; le scan Python et le provider ne chargent aucun fichier
d’exclusion (`--ignorefile ""`). Le filtrage Trivy ajoute le chemin et le PURL du paquet,
version comprise. Les tests de conversion conservent les identifiants de paquets
des rapports réels pour vérifier ces filtres. L'empreinte borne aussi tout le contenu.

| Exécutable Linux amd64 | Version | SHA-256 du binaire extrait |
| --- | --- | --- |
| actionlint | 1.7.12 | `c872d6db8c6bf83a8eaa704fc93999f027d55dffbc63b8a6abdccb47df5f4cd4` |
| gitleaks | 8.30.1 | `88f91962aa2f93ac6ab281d553b9e125f5197bbbce38f9f2437f7299c32e5509` |
| tofu | 1.13.2 | `949061cbb3c3d4558928ca9a459a5052b8c5e5545d17656f33316d2e3bc335f2` |

### Méthode et limites

Les archives de sources officielles des tags épinglés ont été examinées avec
`go list -mod=readonly -deps -json` sur les points d'entrée `cmd/actionlint`,
la racine Gitleaks et `cmd/tofu`, sans modifier leurs graphes. Les imports des
packages applicatifs et dépendances ont été comparés aux packages des avis Go.
L'outil d'analyse temporaire utilise Go 1.27.3 : cela ne change pas le Go embarqué
dans les exécutables et ne démontre pas qu'ils sont corrigés.

Les noms des fonctions ELF ont été lus depuis `.gopclntab` avec `debug/elf` et
`debug/gosym` de Go 1.27.3, sans exécuter les binaires pendant cette inspection.
Cette lecture corrobore les sources ; elle ne suffit pas seule à exclure les
fonctions pouvant être intégrées par le compilateur dans leurs appelants.
Les exclusions combinent donc absence d'import, absence d'appel de l'API ou
précondition de plateforme/configuration impossible, et inspection du binaire.

`govulncheck` 1.9.0, base Go du 21 octobre 2026, complète l'examen. Pour ces
exécutables **stripped**, son [mode binaire revient à une précision au niveau des
modules](https://github.com/golang/vuln/blob/v1.9.0/internal/vulncheck/binary.go#L105-L118)
lorsqu'il ne récupère pas les symboles. Les fonctions de ces rapports ne sont
donc pas une preuve de leur présence ou de leur accessibilité. Ce cas diffère de
`gosu`, dont la table des symboles est disponible.

### Preuves par famille

| Code | Preuve de non-applicabilité et sources |
| --- | --- |
| A-IMPORT | 22 CVE actionlint : aucun import des packages affectés dans le graphe de `cmd/actionlint`, corroboré par l'absence de fonctions correspondantes dans l'ELF. Le binaire ne contient pas les chemins HTTP/TLS/X.509, DNS, mail, XML, ASN.1 ou `html/template` visés. Les URI Docker sont seulement parsées localement. Sources : [commande](https://github.com/rhysd/actionlint/blob/v1.7.12/command.go), [contrôle Docker](https://github.com/rhysd/actionlint/blob/v1.7.12/rule_action.go), [formatage avec text/template](https://github.com/rhysd/actionlint/blob/v1.7.12/error.go). |
| A-URL | CVE-2026-56860 : `rule_action.go` appelle `url.Parse`, pas `URL.Parse`, `URL.ResolveReference` ni `resolvePath`. Aucun appel des API de résolution relative dans les sources importées ; ces fonctions ne figurent pas dans l'ELF. Parser une URI ne remplit pas la précondition de résolution de chemins relatifs de [l'avis Go](https://pkg.go.dev/vuln/GO-2026-6218). |
| ROOT | CVE-2026-39822 dans actionlint et Gitleaks : aucune utilisation de `os.Root`, `os.OpenRoot` ou `os.OpenInRoot` dans les sources applicatives et dépendances importées ; aucune fonction Root affectée dans les ELF. Les appels ordinaires `os.Open` / `os.ReadFile` ne sont pas les API visées par [l'avis Go](https://pkg.go.dev/vuln/GO-2026-4970). |
| G-SSH | 11 CVE : aucun import de `golang.org/x/crypto/ssh`, `ssh/agent` ou `ssh/knownhosts` dans le graphe Gitleaks ; aucun symbole SSH correspondant dans l'ELF. Le module x/crypto dans les métadonnées ne signifie pas que tous ses packages sont utilisés. Le [scan Git](https://github.com/gitleaks/gitleaks/blob/v8.30.1/sources/git.go) lance le Git système pour lire l'historique et les diffs ; il n'ouvre pas de session via cette bibliothèque Go. Cette exclusion ne couvre pas la sécurité du Git système. |
| G-PRECIS | CVE-2026-56851 : package `golang.org/x/text/secure/precis` absent du graphe Gitleaks et de l'ELF ; le profil Nickname de [l'avis](https://pkg.go.dev/vuln/GO-2026-6629) n'est pas utilisé. L'autre alerte x/text sur `unicode/norm` reste active. |
| LINUX | CVE-2026-39836 dans Gitleaks : [l'avis](https://pkg.go.dev/vuln/GO-2026-4971) concerne le traitement NUL sous Windows. L'empreinte autorisée est celle de l'exécutable Linux amd64. Les autres vulnérabilités réseau ne sont pas exclues sur ce fondement. |
| G-S2 | CVE-2026-63209 : [l'avis officiel](https://github.com/klauspost/compress/security/advisories/GHSA-259r-337f-4rfw) requiert `s2.NewDict` puis `Dict.Encode` avec un dictionnaire malveillant. Aucun appel de `s2.NewDict` dans les packages importés, ni symbole de ces deux API dans l'ELF ; [archives 0.1.2](https://github.com/mholt/archives/blob/v0.1.2/sz.go) utilise le lecteur de flux `s2.NewReader`, sans dictionnaire fourni. La profondeur d'archive à zéro n'est pas utilisée comme preuve : l'identification du format précède cette limite. |
| T-SUMDB | Deux CVE x/mod : le [hachage des providers](https://github.com/opentofu/opentofu/blob/v1.13.2/internal/getproviders/hash.go) utilise `sumdb/dirhash` ; `golang.org/x/mod/sumdb` et `sumdb/tlog` sont absents du graphe `cmd/tofu` et de l'ELF. Le client Go de téléchargement et de validation des modules visé n'est pas utilisé par l'exécutable OpenTofu. |
| T-XDS | CVE-2026-84445 : [l'avis](https://github.com/grpc/grpc-go/security/advisories/GHSA-2v4p-qf9q-27wj) requiert un serveur avec routage xDS. Les serveurs de plugins utilisent [grpc.NewServer](https://github.com/hashicorp/go-plugin/blob/v1.8.0/grpc_server.go), sans `xds.NewGRPCServer`. L'import xDS provient de [googledirectpath](https://github.com/grpc/grpc-go/blob/v1.83.1/xds/googledirectpath/googlec2p.go), pour enregistrer les résolveurs/balancers clients. Ni le constructeur de serveur xDS ni `RouteAndProcess` ne figurent dans l'ELF. Cette preuve ne concerne pas la CVE HTTP/2 restante. |

### Risques acceptés et contrôles ciblés

- **Provider / CVE-2026-111943** : le [transport HTTPS](https://github.com/bpg/terraform-provider-proxmox/blob/v0.118.0/proxmox/api/client.go) utilise la validation X.509 système. La protection supplémentaire contre des intermédiaires compromis manque au Go embarqué. Vérifier la CA et la chaîne Proxmox, la mise à jour du magasin de confiance et garder `insecure = false`. Un réseau privé ne constitue pas un correctif ; attendre un artefact reconstruit avec Go corrigé.
- **OpenTofu / CVE-2026-78669** : client HTTP/2 embarqué et transports gRPC présents ; une réponse de pair malveillant pourrait épuiser les ressources. L'absence de serveur HTTP public ne suffit pas à exclure les chemins clients. Vérifier les destinations/providers/modules autorisés et attendre x/net 0.60.0 dans une release officielle.
- **Gitleaks / CERT et TLS** : les chemins TLS et X.509 sont présents dans les imports et le binaire. Les scans locaux n'établissent pas leur accessibilité dans tous les chemins indirects. Pour la CRITICAL CVE-2025-68121, vérifier précisément reprise de session et modification de CA/configuration ; pour les autres, vérifier construction des chaînes et messages TLS. Aucune exclusion sur la seule absence de connexion observée.
- **Gitleaks / mail et MIME** : [go-gitdiff](https://github.com/gitleaks/go-gitdiff/blob/v0.9.1/gitdiff/patch_header.go) importe `net/mail` pour les en-têtes de patch. Des en-têtes ou messages manipulés peuvent exposer les parseurs à un déni de service ; conserver les alertes et vérifier les entrées de l'historique, sans exécuter de charge malveillante sur ce dépôt.
- **Gitleaks / unicode/norm** : le package est importé par afero. La circulation d'UTF-8 invalide jusqu'aux fonctions touchées n'est pas exclue. Vérifier les chemins de fichiers et les appels de normalisation ; attendre x/text corrigé.
- **Gitleaks / autres RÉSEAU et PARSEUR** : `net/http`, `net/url`, ASN.1, XML et `html/template` sont importés indirectement ou pour d'autres formats. L'[HTTP de diagnostic](https://github.com/gitleaks/gitleaks/blob/v8.30.1/cmd/diagnostics.go) est désactivé et le rapport demandé est JSON, mais cela ne prouve pas l'absence de tous les chemins indirects. Conserver les alertes ; tout changement de diagnostics, format ou configuration impose une nouvelle analyse. Garder les durées CI limitées et les contributions externes sans secrets.

Ces contrôles réduisent l'exposition sans supprimer les vulnérabilités. Une
vérification fonctionnelle réussie ou une CI verte avec ces acceptations ne démontre
pas que les vulnérabilités sont corrigées ou inexploitables.

## Contrôles d'exploitation

- Valider les ACL effectives sur la VM, le nœud et chaque stockage. Le token ne
  reçoit aucun droit système à la racine du cluster. `Sys.AccessNetwork` permet
  toutefois des requêtes émises par le nœud : protéger le token et les sorties réseau.
- Filtrer SSH et les ports PostgreSQL au niveau Proxmox ou du réseau. Le projet
  ne configure pas de filtrage ni de TLS SQL ; utiliser un réseau de confiance.
- Le compte SQL initial est superutilisateur de son instance. Protéger ses accès ;
  les rôles applicatifs à permissions fines restent une évolution suivie.
- Prévoir une sauvegarde externe et tester sa restauration. Toutes les bases
  dépendent de la même VM et de son disque ; leur suppression menace les données.
- Lors de la recette, vérifier les locales, collations et extensions nécessaires
  avec PostgreSQL Alpine, qui utilise musl, ainsi que la persistance après recréation
  d'un conteneur. Voir la [recette de test](maintenance.md#vérification-sur-un-environnement-de-test).

## Réexamen

À chaque mise à jour de dépendance et lors du scan quotidien, examiner les
rapports `.reports/`, les releases amont et les exceptions. Retirer une exception
si elle ne correspond plus au binaire ou si une distribution corrigée est retenue.
Ne renouveler l'échéance de 30 jours qu'après nouvelle vérification documentée.
Les alertes nouvelles restent bloquantes ; une exception de non-applicabilité
expirée est réactivée par Trivy. Revoir les risques acceptés au moins mensuellement
et à chaque changement de dépendance ; retirer les entrées corrigées du registre
d’acceptation et ne pas étendre une acceptation à une nouvelle version sans examen. Le [guide de maintenance](maintenance.md#mise-à-jour-des-dépendances)
décrit la mise à jour des versions et empreintes.


## Surveillance des correctifs

La [veille quotidienne](verification.md#notifications-discord-des-correctifs)
recherche des releases stables officielles du provider Proxmox, d'OpenTofu et de
Gitleaks, qui portent les risques actuellement acceptés. Elle vérifie le SHA-256
publié par GitHub, extrait seulement le binaire Linux amd64 sans l'exécuter et
le rescanne sans exclusions à toutes les sévérités. Une baisse de gravité seule
ne suffit pas à annoncer un correctif. Une notification indique les CVE suivies qui ne sont
plus détectées et le nombre d'autres CVE HIGH/CRITICAL encore présentes.
Sans nouvelle version ou correction à notifier, une veille réussie envoie une confirmation
Discord à chaque exécution. Cette confirmation ne signifie pas que les risques
connus ont disparu. Une veille en erreur n’envoie pas de confirmation de réussite.
Une nouvelle version seule, un scan vide ou un contrôle en erreur ne permettent
pas d'annoncer un correctif. La disparition d'une détection Trivy ne remplace pas
la validation fonctionnelle et la revue des avis amont avant toute mise à jour.

Les nouvelles versions stables du provider et d’OpenTofu sont signalées même
sans CVE active ou correctif confirmé. Gitleaks reste suivi pour les corrections
des CVE actives. Une alerte de version ne garantit pas l’absence de vulnérabilités.

Cette veille n'installe rien et ne modifie ni les versions épinglées, ni les
acceptations. PostgreSQL/gosu, les autres outils et les alertes de sévérité plus
faible restent à examiner dans la maintenance des dépendances.
