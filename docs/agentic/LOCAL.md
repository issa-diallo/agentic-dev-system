# Utilisation personnelle locale

Cette méthode est installée sous `.agentic-local/`, exclu de Git par
`info/exclude`. Aucun fichier racine de l’équipe n’est remplacé et aucun hook
n’est activé. L’installation ne lance pas un service : l’agent lit ces instructions
sur demande explicite.

## Activation

> Lis d’abord les règles du dépôt et de l’équipe. Utilise ensuite
> .agentic-local/docs/agentic/LOCAL.md et EXISTING_PROJECT.md dans le même dossier
> pour traiter le ticket <identifiant>.

Les règles de l’équipe priment sur les conventions personnelles, y compris les
commits, branches, outils autorisés et validations. Les AGENTS.md et COMMITS.md
livrés dans `.agentic-local/` sont des références complémentaires, pas des
remplacements des règles du dépôt.

## Résolution des chemins

Dans les documents de la méthode, résoudre les chemins `docs/agentic/`,
`docs/product/`, `docs/adr/`, `COMMITS.md` et `scripts/agentic-check.sh` relatifs
à `.agentic-local/` pour les artefacts personnels. Lire aussi les documents
réels de l’équipe à la racine du dépôt lorsqu’ils existent. Lire le README,
le code et les tests dans le vrai projet ; exécuter les commandes applicatives
à sa racine. Ne pas déplacer le code dans le dossier de la méthode.

Stocker Research, Design, Plan, Verify, Review et Handoff dans
`.agentic-local/docs/agentic/work/<ticket>/`. Une décision architecturale qui
concerne l’équipe doit suivre son processus de validation ; une note locale ne
remplace pas une décision approuvée.

Contrôle de présence :

```bash
(cd .agentic-local && bash scripts/agentic-check.sh --existing)
```

`git status --short` doit rester inchangé après installation. Les exclusions
ne protègent pas d’un `git add -f` : contrôler le diff staged avant commit.
Un nouveau worktree a son propre contenu : y relancer l’installation locale
si nécessaire. Git résout l’emplacement des exclusions, y compris en worktree.

## Mise à jour

Une seconde installation refuse le dossier existant. Comparer les versions et
sauvegarder les notes personnelles avant une mise à jour manuelle. Ne pas forcer
l’écrasement et ne pas supprimer les artefacts d’une story en cours.
