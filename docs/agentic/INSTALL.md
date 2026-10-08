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

## Projet existant : usage personnel local

```bash
./install-agentic.sh --local /chemin/vers/le-projet
```

Le projet cible doit être la racine d’un dépôt Git. La méthode est placée dans
`.agentic-local/`, ajouté à l’exclusion Git locale (résolue aussi en worktree).
Aucun fichier de l’équipe, `.gitignore`, hook ou template GitHub n’est modifié.
Aucun document produit n’est généré. Si les règles `.gitignore` de l’équipe
rendent ces fichiers visibles malgré l’exclusion locale, l’installation refuse
et restaure le contenu précédent de `info/exclude`. Les fichiers déjà suivis ne sont jamais
masqués : un chemin `.agentic-local` suivi provoque un refus.

L’installation n’active pas automatiquement l’agent. Utiliser le prompt et les
règles de résolution des chemins de [LOCAL.md](LOCAL.md). Les conventions de
l’équipe priment, notamment pour les commits.

## Projet existant : installation partageable

```bash
./install-agentic.sh --existing /chemin/vers/le-projet
```

Installe le socle aux chemins standards, sans créer `docs/product/` ni `docs/adr/`.
Ces fichiers ne sont pas exclus de Git. S’il existe déjà AGENTS.md, COMMITS.md
ou docs/agentic, l’installation refuse avant copie ; utiliser --local pour
conserver les règles de l’équipe.

## Protection et mise à jour

Les collisions sont contrôlées avant la création des dossiers. Une installation
fraîche fonctionne sans FORCE. Les fichiers optionnels existants sont conservés.
Les artefacts `docs/agentic/work/` du dépôt source ne sont jamais distribués.

`FORCE=1` est désormais refusé : comparer et sauvegarder les fichiers avant une
mise à jour manuelle. Une seconde installation locale refuse également d’écraser
les notes personnelles.

## Prompt de démarrage

Pour l’entrée EXISTING (ticket cadré sur projet existant), utiliser le prompt de
[EXISTING_PROJECT.md](EXISTING_PROJECT.md) et le contrôle `bash scripts/agentic-check.sh --existing`.
Les templates produit copiés ne constituent pas des gates PASS.

Pour l’entrée PRODUCT, une fois installé :

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
