# Utilisation personnelle locale

Par défaut (ou avec `--local`), cette méthode est installée sous `.agentic-local/`, exclu de Git par
`info/exclude`. Aucun fichier racine de l’équipe n’est remplacé et aucun hook
n’est activé. L’installation ne lance pas un service : l’agent lit ces instructions
sur demande explicite.

## Activation

> Lis d’abord les règles du dépôt et de l’équipe. Utilise ensuite
> .agentic-local/docs/agentic/LOCAL.md et l’index de méthode dans le même dossier.
> Pour un ticket cadré, utilise EXISTING_PROJECT.md ; pour un nouveau produit ou
> un gros périmètre, prépare les six rubriques adaptées avant BUILD.

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
sous `.agentic-local/docs/product/`. Les documents métier approuvés que l’équipe
souhaite partager peuvent ensuite être versionnés dans ses chemins habituels.
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
exclusions cassées, sans hook ni changement de configuration Git. Les documents
métier, ADR, règles AGENTS d’équipe et configurations applicatives sont permis.
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

Les scripts V2, profils `codex/agents/` et six skills `skills/` restent sous le
socle exclu. Depuis la racine métier, `bash .agentic-local/scripts/agentic-codex.sh run "Mission"`
active les profils et demande la lecture du socle avec la mission comme prompt.
Sans `run`, seuls les profils sont configurés pour cette invocation. Les règles équipe sont
prioritaires ; les permissions, compte et arguments restent ceux de Codex.
Aucun service permanent ni agent actif n’est déduit des fichiers. Les skills sont
routés depuis la racine explicite `.agentic-local/skills` et chargés à la demande.
Voir [INSTALL](INSTALL.md#distribution-v2-et-activation-codex) pour compatibilité et
limites. Revenir à Codex normal désactive les overrides sans modifier de fichiers.
