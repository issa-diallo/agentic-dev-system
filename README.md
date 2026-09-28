# Agentic Dev System

Système privé et réutilisable pour préparer, exécuter et vérifier le développement multi-agents.

## Objectif

**Préparer les tâches assez clairement pour gagner du temps pendant
l'implémentation.**

Le même système fonctionne pour :
- petit projet → mode LIGHT ;
- projet normal → mode STANDARD ;
- gros projet / multi-agents / production sensible → mode LARGE.

## Pipeline

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
Worktree Setup
 ↓
Execute
 ↓
Verify / Evidence
 ↓
Review
 ↓
Goal satisfied?
 ↓
Ship
```

## Installation

```bash
git clone git@github.com:issa-diallo/agentic-dev-system.git
./agentic-dev-system/install-agentic.sh /chemin/vers/mon-projet
```

## Principes

- préparer avant de coder ;
- choisir la profondeur adaptée au risque ;
- verrouiller les décisions structurantes dans Architecture/ADR ;
- isoler les stories significatives par worktree ;
- prouver que le résultat fonctionne ;
- séparer implémentation et review ;
- utiliser des goals mesurables pour les longues tâches ;
- protéger les actions destructrices ;
- garder le contexte agentique propre ;
- automatiser les contrôles répétables.

Commencer par `docs/agentic/METHOD.md` puis `docs/agentic/SCALING.md`.
