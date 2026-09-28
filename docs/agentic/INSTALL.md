# Installation

La méthode est conçue pour être installée dans n'importe quel projet.

## Depuis un clone local du dépôt de la méthode

```bash
./install-agentic.sh /chemin/vers/mon-projet
```

Depuis le dossier du projet cible :

```bash
/path/to/agentic-method/install-agentic.sh .
```

L'installateur ajoute :

```text
AGENTS.md
COMMITS.md
docs/agentic/
docs/product/PRD.md
docs/product/STORIES.md
docs/product/STORY_REVIEW.md
docs/product/ARCHITECTURE.md
docs/product/DESIGN_SYSTEM.md
docs/agentic/work/
```

## Protection

L'installateur refuse d'écraser :

- un `AGENTS.md` existant ;
- un `COMMITS.md` existant ;
- un dossier `docs/agentic` existant.

Pour remplacer volontairement une installation existante :

```bash
FORCE=1 ./install-agentic.sh /chemin/vers/mon-projet
```

Utiliser `FORCE=1` avec prudence.

## Prompt de démarrage

Une fois installé :

> Lis AGENTS.md, COMMITS.md et docs/agentic/METHOD.md. Applique strictement PRD → Stories → Story Review → Architecture → Design System → Research → Design → Plan → Execute → Review → Ship. Identifie la première phase qui n'est pas PASS et commence uniquement par celle-ci. Pour chaque commit, utilise le Gitmoji approprié et respecte COMMITS.md.

## Commits

Chaque projet installé reçoit `COMMITS.md`.

Les agents doivent :

- choisir le Gitmoji correspondant à l'intention réelle ;
- utiliser un titre impératif court ;
- expliquer le pourquoi dans le corps ;
- ajouter `Fixes #<issue_number>`.

La référence Gitmoji est https://gitmoji.dev/.

## Mise à jour

Pour mettre à jour la méthode dans un projet existant, comparer d'abord les changements entre la version installée et la nouvelle version. Ne pas écraser automatiquement des règles projet personnalisées.
