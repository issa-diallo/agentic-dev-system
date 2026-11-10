# Utilisation personnelle locale

Par défaut (ou avec `--local`), cette méthode est installée sous `.agentic-local/`, exclu de Git par
`info/exclude`. Aucun fichier racine de l’équipe n’est remplacé. Les profils
natifs sont ajoutés sous `.codex/agents/` et `.claude/agents/`, avec exclusions
ciblées ; le hook `pre-push` est installé si aucun hook existant ne le bloque. L’installation ne lance pas un service : l’agent lit ces instructions
sur demande explicite.

## Activation

Avant la première mission de développement, appliquer le questionnaire de
[premier lancement](ONBOARDING.md), vérifier les connexions et tester les modèles
avant d’enregistrer les choix. Une configuration complète évite de reposer les
questions. Conserver le chemin `config` renvoyé et le passer explicitement à
chaque commande du runner. Une demande d’aide, de lecture, de statut ou le message
exact `agentic ?` reste sans questionnaire ni inférence.

> Lis d’abord les règles du dépôt et de l’équipe. Utilise ensuite
> .agentic-local/docs/agentic/LOCAL.md et l’index de méthode dans le même dossier.
> Pour un ticket cadré, utilise EXISTING_PROJECT.md ; pour un nouveau produit ou
> un gros périmètre, prépare les six rubriques adaptées avant BUILD.

### Garde avant publication

L'installation pose un hook Git `pre-push` local qui refuse un `git push` de
branche sans `pr-split.json` valide ni fichiers dans le périmètre déclaré. Elle
ne remplace jamais un hook existant et ignore `core.hooksPath` (message à la
fin de l'installation). Détails et contournement visible dans
[PR_SPLIT](templates/PR_SPLIT.md#garde-avant-publication).

### Activation permanente avec `codex` nu

Sans fichier à la racine, `codex` seul ne lit pas `.agentic-local/` : la méthode
n'est alors pas appliquée (PR_SPLIT sauté, une seule grosse PR). Codex charge au
démarrage d'une session neuve le fichier personnel `~/.codex/AGENTS.md`
(`$CODEX_HOME/AGENTS.md` si défini). L'installation locale le crée s'il n'existe
pas, avec le contenu de `codex/global-AGENTS.md` du service, et ne remplace jamais
un fichier existant (un fichier déjà présent doit contenir ces règles). Le lanceur
`.agentic-local/scripts/agentic-codex.sh run "<mission>"` reste possible.

Vérifier dans une session neuve : écrire `agentic ?`. Codex lit `.agentic-local/`,
contrôle le hook `pre-push` puis répond « Agentic Dev System prêt à commencer. » ou « Agentic Dev System NON prêt : »
suivi de la raison. Toute autre réponse : le fichier global est absent ou ancien.

Les règles de l’équipe priment sur les conventions personnelles, y compris les
commits, branches, outils autorisés et validations. Les AGENTS.md et COMMITS.md
livrés dans `.agentic-local/` sont des références complémentaires, pas des
remplacements des règles du dépôt.

## Résolution des chemins

Dans les documents de la méthode, résoudre les chemins `docs/agentic/`,
`docs/product/`, `docs/adr/`, `COMMITS.md` et `scripts/agentic*.sh` relatifs
à `.agentic-local/` pour les artefacts personnels. Lire aussi les documents
réels de l’équipe à la racine du dépôt lorsqu’ils existent. Lire le README,
le code et les tests dans le vrai projet ; exécuter les commandes applicatives
à sa racine. Ne pas déplacer le code dans le dossier de la méthode.

Pour un nouveau produit, préparer les six rubriques avec le template PREPARE
sous `.agentic-local/docs/agentic/work/<ticket>/`. Cette préparation reste hors
Git, même approuvée ou destinée à l'équipe. Aucun déplacement vers un chemin
métier ne doit l'introduire dans une PR. Voir [PULL_REQUESTS](PULL_REQUESTS.md).
Le mode d’installation local ne change pas le choix du pipeline ni ses gates.

Stocker le delta PREPARE, les preuves Verify/Review et Handoff dans
`.agentic-local/docs/agentic/work/<ticket>/`. Une décision architecturale qui
concerne l’équipe doit suivre son processus de validation ; une note locale ne
remplace pas une décision approuvée.

Contrôle de présence :

```bash
(cd .agentic-local && bash scripts/agentic-check.sh --existing)
```

`git status --short` doit rester inchangé après installation. Les exclusions
protègent `git add -A` et `git add .`, mais pas `git add -f` ou un fichier
déjà suivi. Après staging métier explicite, contrôler le diff et utiliser :

```bash
bash .agentic-local/scripts/agentic-commit.sh -F /chemin/vers/message-commit.txt
```

Le wrapper fait le contrôle automatique staged avant chaque commit du workflow.
Il refuse les chemins personnels (sources de rename/copy comprises) et les
exclusions cassées, sans hook ni changement de configuration Git. Les règles
AGENTS d'équipe et configurations applicatives sont permises ; leur nom ou le
chemin d'un document ne dispense pas de vérifier son contenu. Les plans et
rapports de mission restent interdits même hors des chemins reconnus par la garde.
Pour classer des fichiers personnels hérités et retirer seulement leur index
après accord explicite, suivre [INSTALL](INSTALL.md#migrer-une-installation-ancienne).
Un commit Git direct hors workflow échappe à ce contrôle ; ne pas l’utiliser
pour contourner un refus. Les règles de messages de l’équipe restent prioritaires.

Un nouveau worktree a son propre contenu : y relancer l’installation locale
si nécessaire. Git résout l’emplacement des exclusions, y compris en worktree.

## Mise à jour

Une seconde installation refuse le dossier existant. Comparer les versions et
sauvegarder les notes personnelles avant une mise à jour manuelle. Ne pas forcer
l’écrasement et ne pas supprimer les artefacts d’une story en cours.


## Capacités V2 locales

Pour Claude Code : `bash .agentic-local/scripts/agentic-claude.sh run "Mission"`. Pour déléguer l'implémentation à un modèle économique : [DELEGATION](DELEGATION.md) (config personnelle sous `.agentic-local/`, hors Git).

Les scripts et sources canoniques des profils restent dans le socle exclu. Les
copies chargées nativement sont placées dans `.codex/agents/` et `.claude/agents/`
à la racine du projet. En LOCAL, leurs six chemins exacts sont exclus de Git.
Les profils tiers et configurations existantes ne sont pas remplacés.

Ouvrir une nouvelle session du client après installation, en respectant sa
politique de confiance. Les lanceurs `agentic-codex.sh` et `agentic-claude.sh`
transmettent seulement les arguments et, avec `run`, les lectures de méthode et
la mission. Ils n’injectent plus de profils par `config_file` ou `--agents`.
Codex/Claude lancés normalement conservent la découverte des copies natives.

La mise à jour du socle synchronise les copies natives intactes ; les copies
personnalisées restent préservées et signalées. Voir
[INSTALL](INSTALL.md#distribution-v2-et-activation-codex) pour les commandes,
les sources officielles et les preuves de découverte observées sur les CLI.
La présence et la découverte d’un profil ne prouvent pas le lancement d’un agent :
conserver les reçus du runtime et une review indépendante. Les permissions et
modèles ne sont jamais modifiés automatiquement par l’installation.
