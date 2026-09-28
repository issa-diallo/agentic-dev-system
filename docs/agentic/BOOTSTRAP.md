# Bootstrap — installer la méthode dans un nouveau projet

Ce document rend le système reproductible.

## 1. Copier le socle

Copier dans le nouveau repo :

```text
AGENTS.md
docs/agentic/
```

Créer ensuite :

```text
docs/product/
docs/agentic/work/
```

## 2. Initialiser les documents produit

Copier les templates :

```text
docs/agentic/templates/PRD.md           -> docs/product/PRD.md
docs/agentic/templates/STORIES.md       -> docs/product/STORIES.md
docs/agentic/templates/STORY_REVIEW.md  -> docs/product/STORY_REVIEW.md
docs/agentic/templates/ARCHITECTURE.md  -> docs/product/ARCHITECTURE.md
docs/agentic/templates/DESIGN_SYSTEM.md -> docs/product/DESIGN_SYSTEM.md
```

Ne pas remplir les phases suivantes tant que le gate précédent n'est pas PASS.

## 3. Commande/prompt de démarrage

Donner à l'agent :

> Lis AGENTS.md et docs/agentic/METHOD.md. Applique strictement le pipeline PRD → Stories → Story Review → Architecture → Design System → Research → Design → Plan → Execute → Review → Ship. Commence par la première phase non terminée. Ne saute aucune phase. À chaque phase, produis l'artefact prévu et indique PASS ou BLOCKED.

## 4. Après validation du produit

Pour chaque story :

1. créer une issue ;
2. créer `docs/agentic/work/<story>/` ;
3. copier RESEARCH.md, DESIGN.md, PLAN.md, REVIEW.md, HANDOFF.md ;
4. créer une branche/worktree ;
5. exécuter Research → Design → Plan → Execute → Review → Ship.

## 5. Checklist de portabilité

- [ ] AGENTS.md présent à la racine
- [ ] METHOD.md présent
- [ ] WORKFLOW.md présent
- [ ] templates présents
- [ ] PRD créé
- [ ] Stories créées
- [ ] Story Review passée
- [ ] Architecture documentée
- [ ] Design System documenté
- [ ] STATUS.md initialisé
- [ ] règles CI définies avant Ship
