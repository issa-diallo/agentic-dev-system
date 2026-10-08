# Agentic Dev System

Système privé et réutilisable pour préparer, exécuter et vérifier le développement multi-agents.

## Objectif

**Préparer les tâches assez clairement pour gagner du temps pendant
l'implémentation.**

Le même système fonctionne pour :
- petit projet → mode LIGHT ;
- projet normal → mode STANDARD ;
- gros projet / multi-agents / production sensible → mode LARGE.

## Projet existant sans documentation produit

Pour un ticket cadré, démarrer à Research sans recréer les cinq documents produit.
Suivre [l’entrée projet existant](docs/agentic/EXISTING_PROJECT.md), puis Design → Plan →
Execute → Verify → Review → Ship, avec isolation et Goal lorsque requis.
Un nouveau produit ou gros périmètre conserve le pipeline complet.

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

Pour un usage personnel dans un dépôt d’entreprise :

```bash
./agentic-dev-system/install-agentic.sh --local /chemin/vers/le-projet
```

La méthode reste dans `.agentic-local/`, exclu de Git, sans modifier les fichiers
de l’équipe. Voir [l’installation](docs/agentic/INSTALL.md) pour l’activation
explicite et le mode partageable `--existing`.

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

Commencer par [l’index conditionnel](docs/agentic/README.md), puis choisir le mode.
