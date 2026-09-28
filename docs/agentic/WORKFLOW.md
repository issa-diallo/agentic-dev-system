# Workflow canonique

Le workflow officiel est :

`PRD -> Stories -> Story Review -> Architecture -> Design System -> Research -> Design -> Plan -> Execute -> Review -> Ship`

Voir `METHOD.md` pour la logique complète.

# A. Pipeline Produit

## 1. PRD

Créer `docs/product/PRD.md`.

Gate PASS si :
- problème clair ;
- utilisateurs définis ;
- scope et non-scope explicites ;
- parcours/capacités principales ;
- critères de succès ;
- contraintes et risques connus.

## 2. Stories

Créer `docs/product/STORIES.md`.

Chaque story est une tranche livrable fonctionnelle et testable.

## 3. Story Review

Créer `docs/product/STORY_REVIEW.md`.

La review doit détecter :
- trous fonctionnels ;
- dépendances circulaires ;
- stories trop larges ;
- critères insuffisants ;
- ordre incorrect.

Si Critical/Major : revenir à Stories.

## 4. Architecture

Créer `docs/product/ARCHITECTURE.md`.

Les décisions structurantes doivent être fixées avant la phase story-level.

## 5. Design System

Créer `docs/product/DESIGN_SYSTEM.md`.

Le système visuel/interface devient une contrainte pour les designs de story.

# B. Pipeline par Story

## 6. Research

Créer :

`docs/agentic/work/<story>/research.md`

Analyser le repo réel, les dépendances, conventions, risques, tests et zones impactées.

## 7. Design

Créer :

`docs/agentic/work/<story>/design.md`

Définir précisément l'expérience, les états, contrats, flux ou écrans.

## 8. Plan

Créer :

`docs/agentic/work/<story>/plan.md`

Le plan doit permettre à un autre agent d'implémenter sans refaire les décisions précédentes.

## 9. Execute

Créer branche + worktree.

Implémenter le plan. Ajouter les tests. Produire `handoff.md`.

## 10. Review

Un agent indépendant produit `review.md`.

Critical/Major => retour Execute.

## 11. Ship

Ship comprend obligatoirement :

- commit(s) ;
- push ;
- PR ;
- CI ;
- corrections CI si besoin ;
- validation humaine lorsque prévue ;
- merge ;
- cleanup du worktree ;
- mise à jour STATUS.

# C. Parallélisme

Après Architecture + Design System PASS, plusieurs stories peuvent avancer en parallèle si leurs dépendances le permettent.

```text
Story A: Research -> Design -> Plan -> Execute -> Review -> Ship
Story B: Research -> Design -> Plan -> Execute -> Review -> Ship
Story C: Research -> Design -> Plan -> Execute -> Review -> Ship
```

Une dépendance structurante doit être stabilisée avant les stories qui en dépendent.

# D. Reprise d'un projet existant

Un repo existant n'a pas besoin de réécrire artificiellement son histoire.

Créer :
- PRD "as-is + target" ;
- Stories restantes ;
- Story Review ;
- Architecture actuelle ;
- Design System actuel.

Puis reprendre chaque nouvelle story à Research.
