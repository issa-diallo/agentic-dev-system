# Reusable Agentic Development Method

Cette méthode est conçue pour être copiée dans n'importe quel dépôt logiciel.

## La chaîne à mémoriser

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

Acronyme mental possible :

`P-S-S-A-D-R-D-P-E-R-S`

Le nom importe moins que l'ordre.

## Deux niveaux

### Niveau Produit — exécuté au démarrage ou lors d'un changement majeur

1. PRD
2. Stories
3. Story Review
4. Architecture
5. Design System

Ce niveau transforme une idée en système explicite.

### Niveau Story — répété pour chaque unité livrable

6. Research
7. Design
8. Plan
9. Execute
10. Review
11. Ship

Ce niveau transforme une story validée en changement livré.

## Règle d'or

Aucune phase ne doit inventer ce que la phase précédente devait décider.

Exemples :

- Execute ne redéfinit pas le besoin.
- Execute ne change pas la stack.
- Plan ne redéfinit pas l'architecture.
- Design ne réécrit pas les critères d'acceptation.
- Research ne modifie pas silencieusement le scope.
- Ship ne masque pas une review en échec.

## Gate universel

Chaque phase doit répondre à trois questions :

1. Quel artefact a été produit ?
2. Quel est le verdict : PASS ou BLOCKED ?
3. Quelles informations deviennent des contraintes pour la phase suivante ?

Sans artefact et verdict, la phase n'est pas terminée.

## Phase 1 — PRD

But : définir le produit, le problème, les utilisateurs, la valeur, le périmètre, le non-périmètre et les critères de succès.

Sortie : `docs/product/PRD.md`.

## Phase 2 — Stories

But : découper le PRD en tranches fonctionnelles livrables.

Chaque story doit avoir :
- acteur ;
- besoin ;
- valeur ;
- critères d'acceptation ;
- dépendances ;
- hors périmètre ;
- complexité approximative.

Sortie : `docs/product/STORIES.md`.

## Phase 3 — Story Review

But : challenger le découpage avant tout investissement technique.

Chercher :
- dépendances circulaires ;
- stories trop grosses ;
- stories techniques déguisées en besoin utilisateur ;
- critères absents ;
- fonctionnalités oubliées ;
- doublons ;
- ordre impossible.

Sortie : `docs/product/STORY_REVIEW.md`.

Critical/Major => corriger Stories puis refaire Story Review.

## Phase 4 — Architecture

But : décider les contraintes techniques communes et la stack avant que les agents implémentent chacun leur propre solution.

La phase Architecture doit :

1. partir des contraintes du PRD et des Stories ;
2. identifier les exigences techniques réelles ;
3. comparer les options raisonnables ;
4. sélectionner explicitement la stack ;
5. expliquer pourquoi elle est retenue ;
6. documenter les compromis ;
7. documenter les alternatives rejetées ;
8. créer des ADR pour les décisions structurantes.

Doit couvrir selon le projet :
- structure repo ;
- langages ;
- frontend/backend ;
- protocole/style d'API ;
- données et ORM/data access ;
- auth/authz ;
- multi-tenant ;
- cache ;
- queues/jobs ;
- stockage ;
- sécurité ;
- intégrations ;
- observabilité ;
- CI/CD ;
- hébergement ;
- environnements ;
- stratégie de tests ;
- conventions ;
- ADR nécessaires.

Sorties :

- `docs/product/ARCHITECTURE.md`
- `docs/adr/ADR-XXX-*.md` pour les décisions structurantes.

La stack n'est pas une préférence implicite de l'agent. Elle devient une contrainte de projet après PASS.

Si une story nécessite de remettre en cause une décision d'architecture :
- ne pas changer la stack pendant Execute ;
- marquer la story BLOCKED ;
- revenir à Architecture ;
- créer ou modifier l'ADR ;
- faire valider la nouvelle décision ;
- reprendre ensuite la story.

## Phase 5 — Design System

But : fixer le langage visuel et les composants réutilisables avant de designer chaque story.

Doit couvrir :
- couleurs/tokens ;
- typographie ;
- spacing ;
- layout ;
- composants ;
- états ;
- responsive ;
- accessibilité ;
- patterns de formulaires/navigation/tableaux.

Sortie : `docs/product/DESIGN_SYSTEM.md`.

Pour un projet sans UI, cette phase devient `INTERFACE_SYSTEM` et décrit les conventions d'interface/API/CLI.

## Phase 6 — Research

But : analyser le code réel et déterminer où la story s'intègre.

Research est spécifique à une story.

Research doit respecter les décisions acceptées dans Architecture et les ADR.

Sortie : `research.md`.

## Phase 7 — Design

But : transformer critères + research + design system en expérience/contrat précis.

Pour UI :
- écrans ;
- états loading/empty/error/success ;
- interactions ;
- champs ;
- responsive.

Pour API/CLI/backend :
- endpoints/commands ;
- payloads ;
- erreurs ;
- transitions d'état ;
- diagrammes de flux.

Sortie : `design.md`.

## Phase 8 — Plan

But : produire le plan d'implémentation concret.

Le plan précise :
- fichiers ;
- modèles ;
- contrats ;
- migrations ;
- tests ;
- ordre ;
- risques ;
- rollback.

Le plan ne peut pas remplacer silencieusement une décision d'Architecture ou un ADR accepté.

Sortie : `plan.md`.

## Phase 9 — Execute

But : implémenter le plan, idéalement dans un worktree isolé.

Execute ne doit pas prendre de décision produit majeure ni modifier la stack approuvée.

Sortie :
- code ;
- tests ;
- handoff.

## Phase 10 — Review

But : faire une revue indépendante contre la story, le plan, l'architecture, les ADR et le diff.

Sortie : `review.md`.

Verdicts :
- PASS
- PASS_WITH_MINOR
- CHANGES_REQUIRED
- BLOCKED

Critical/Major => retour Execute, ou retour Architecture si le problème provient d'une décision structurante.

## Phase 11 — Ship

But : livrer proprement.

Ship signifie :
- commit propre ;
- PR ;
- tests/CI ;
- description complète ;
- validation humaine si requise ;
- merge ;
- cleanup worktree ;
- statut DONE.

## Boucles autorisées

```text
Stories <------ Story Review
                  |
                  +-- corrections

Architecture <--- Research/Plan
     |
     +-- si une décision structurante doit changer

Execute <------- Review
   |
   +-- corrections

Ship ---> CI failure ---> Execute/Plan selon cause
```

## Ce qui est interdit

- Idea -> Execute
- PRD -> Execute
- Story -> Execute sans Research/Plan
- Execute -> changement silencieux de stack
- Implementer -> auto-approval
- tests non exécutés présentés comme PASS
- merge d'une story BLOCKED
