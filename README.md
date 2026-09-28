# Agentic Dev System

Système privé et réutilisable de développement multi-agents.

## Pipeline canonique

```text
PRD
 ↓
Stories
 ↓
Story Review
 ↓
Architecture
 ↓
Design System
 ↓
Research
 ↓
Design
 ↓
Plan
 ↓
Execute
 ↓
Review
 ↓
Ship
```

## Installation dans un projet

Clone ce dépôt privé une fois :

```bash
git clone git@github.com:issa-diallo/agentic-dev-system.git
```

Puis installe la méthode dans n'importe quel projet :

```bash
./agentic-dev-system/install-agentic.sh /chemin/vers/mon-projet
```

Ou depuis le projet cible :

```bash
/path/to/agentic-dev-system/install-agentic.sh .
```

L'installateur ajoute :

- `AGENTS.md`
- `docs/agentic/`
- `docs/product/PRD.md`
- `docs/product/STORIES.md`
- `docs/product/STORY_REVIEW.md`
- `docs/product/ARCHITECTURE.md`
- `docs/product/DESIGN_SYSTEM.md`
- `docs/agentic/work/`

## Prompt de démarrage

> Lis AGENTS.md et docs/agentic/METHOD.md. Applique strictement PRD → Stories → Story Review → Architecture → Design System → Research → Design → Plan → Execute → Review → Ship. Identifie la première phase qui n'est pas PASS et commence uniquement par celle-ci.

## Principes

- cadrer avant de coder ;
- une phase produit commune, puis un pipeline par story ;
- un ticket = une branche = un worktree ;
- implémentation et review séparées ;
- artefact + gate PASS/BLOCKED à chaque phase ;
- parallélisme uniquement lorsque les dépendances le permettent ;
- validation humaine avant les merges ou actions sensibles.

Voir `docs/agentic/METHOD.md` pour la définition complète.
