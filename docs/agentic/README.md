# Agentic Development System

Ce dossier contient une méthode portable de développement multi-agents.

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
Execute
 ↓
Review
 ↓
Ship
```

Les cinq premières phases cadrent le produit. Les six suivantes sont répétées pour chaque story.

## Fichiers essentiels

- `METHOD.md` — définition canonique de la méthode
- `BOOTSTRAP.md` — installation dans un nouveau projet
- `WORKFLOW.md` — règles d'exécution
- `STATUS.md` — cockpit des travaux
- `roles/` — responsabilités des agents
- `templates/` — artefacts standardisés

## Règle

Si un agent ne sait pas quelle est la prochaine étape, il doit :

1. lire `METHOD.md` ;
2. identifier le dernier artefact PASS ;
3. exécuter uniquement la phase suivante.

Il ne doit jamais choisir arbitrairement de coder.
