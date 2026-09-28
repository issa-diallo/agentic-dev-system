# Reusable Agentic Development Method

Cette méthode est conçue pour être copiée dans n'importe quel dépôt logiciel.

## Objectif

Préparer suffisamment les tâches pour que l'implémentation soit rapide, claire et presque mécanique.

La méthode doit fonctionner pour les petits comme les gros projets. La profondeur change, pas l'ordre mental.

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
Worktree Setup
 ↓
Execute
 ↓
Verify
 ↓
Review
 ↓
Goal satisfied?
 ↓
Ship
```

Voir `SCALING.md` pour choisir LIGHT, STANDARD ou LARGE.

## Règle d'or

Aucune phase ne doit inventer ce que la phase précédente devait décider.

- Execute ne redéfinit pas le besoin.
- Execute ne change pas la stack.
- Plan ne redéfinit pas l'architecture.
- Design ne réécrit pas les critères d'acceptation.
- Research ne modifie pas silencieusement le scope.
- Verify exige des preuves.
- Review ne se contente pas des affirmations de l'implementer.
- Ship ne masque pas une review ou un goal en échec.

## Gate universel

Chaque phase doit répondre à :
1. Quel artefact a été produit ?
2. Quel est le verdict : PASS ou BLOCKED ?
3. Quelles contraintes deviennent obligatoires pour la suite ?

## Phase Produit

### 1. PRD
Définir problème, utilisateurs, valeur, scope, non-scope, contraintes, risques et succès.

Sortie : `docs/product/PRD.md`.

### 2. Stories
Découper le PRD en tranches fonctionnelles livrables et testables.

Sortie : `docs/product/STORIES.md`.

### 3. Story Review
Challenger couverture, dépendances, taille, critères et ordre.

Sortie : `docs/product/STORY_REVIEW.md`.

### 4. Architecture
Choisir et justifier stack, boundaries, data, API, auth, sécurité, infra, tests et déploiement.

Créer des ADR pour les décisions structurantes.

Sorties :
- `docs/product/ARCHITECTURE.md`
- `docs/adr/*.md`

### 5. Design System
Fixer le langage d'interface commun avant les designs de story.

Sortie : `docs/product/DESIGN_SYSTEM.md`.

## Phase Story

### 6. Research
Analyser le repo réel, les conventions, dépendances, tests, risques et points d'intégration.

Sortie : `research.md`.

### 7. Design
Définir précisément écrans, états, flux, contrats ou comportements.

Sortie : `design.md`.

### 8. Plan
Transformer les décisions précédentes en séquence d'implémentation concrète.

Un bon plan doit minimiser les décisions restantes pendant Execute.

Sortie : `plan.md`.

### 9. Worktree Setup
Pour une story significative, préparer un environnement isolé et reproductible.

Référence : `templates/WORKTREE_ENVIRONMENT.md`.

### 10. Execute
Implémenter le plan. Rester dans le scope. Ajouter les tests.

Sorties :
- code ;
- tests ;
- `handoff.md`.

### 11. Verify
Prouver que le résultat fonctionne.

Evidence possibles :
- tests ;
- build ;
- browser flow ;
- API calls ;
- screenshots ;
- logs ;
- mesures de performance.

Sortie : `verify.md`.

### 12. Review
Faire une revue indépendante contre story, architecture, plan, evidence et diff.

Sortie : `review.md`.

### 13. Goal satisfied?
Pour une tâche longue ou complexe, vérifier les critères mesurables du goal.

Sortie : `goal.md`.

Si aucun goal spécifique n'est nécessaire, les critères d'acceptation + Verify + Review font office de goal.

### 14. Ship
Créer commits/PR, passer CI, obtenir validation humaine si requise, merger et nettoyer.

## Préparation vs exécution

Le système optimise volontairement le travail avant Execute.

```text
Plus de clarté avant Execute
        ↓
moins de décisions pendant Execute
        ↓
moins de retours arrière
        ↓
moins de tokens gaspillés
        ↓
implémentation plus rapide
```

## Context hygiene

Avant les longues tâches, appliquer `CONTEXT.md`.

## Safety

Appliquer `SAFETY.md` et utiliser des hooks quand le harness le permet.

## Ce qui est interdit

- Idea -> Execute
- Story -> Execute sans Research/Design/Plan
- Execute -> changement silencieux de stack
- "ça marche" sans Verify/Evidence
- Implementer -> auto-approval
- tests non exécutés présentés comme PASS
- merge avec Critical/Major ouvert
- merge d'une story BLOCKED
