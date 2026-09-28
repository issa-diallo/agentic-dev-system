# Agentic Project Rules

Ce dépôt applique une méthode reproductible de développement agentique.

## Pipeline obligatoire

Pour tout nouveau produit ou gros périmètre :

`PRD -> Stories -> Story Review -> Architecture -> Design System -> Research -> Design -> Plan -> Execute -> Review -> Ship`

Pour une story déjà cadrée, reprendre à `Research`.

Ne jamais oublier, inverser ou sauter une étape sans justification explicite.

## Source de vérité

Lire dans cet ordre :

1. `README.md`
2. `docs/agentic/METHOD.md`
3. `docs/agentic/WORKFLOW.md`
4. les documents projet dans `docs/product/`
5. le ticket/story concerné
6. les artefacts de travail de la story

## Gates

Chaque phase produit un artefact et un verdict PASS ou BLOCKED. La phase suivante ne démarre que si la précédente est PASS.

### Phase produit
1. PRD
2. Stories
3. Story Review
4. Architecture
5. Design System

### Phase par story
6. Research
7. Design
8. Plan
9. Execute
10. Review
11. Ship

## Règle fondamentale

L'agent principal orchestre. Il ne doit pas coder par réflexe.

L'agent qui implémente ne doit pas être le seul reviewer de son propre travail.

## Isolation d'exécution

Pour toute story non triviale :

- une issue ou identifiant de story ;
- une branche dédiée ;
- un worktree dédié ;
- un implementer ;
- un reviewer indépendant ;
- une PR dédiée.

Convention recommandée :

`worktrees/<ticket>-<slug>`

Branche :

`feat/<ticket>-<slug>`, `fix/<ticket>-<slug>`, `chore/<ticket>-<slug>`.

Deux agents ne modifient jamais le même worktree simultanément.

## Artefacts attendus

### Produit
- `docs/product/PRD.md`
- `docs/product/STORIES.md`
- `docs/product/STORY_REVIEW.md`
- `docs/product/ARCHITECTURE.md`
- `docs/product/DESIGN_SYSTEM.md`

### Story
- `docs/agentic/work/<story>/research.md`
- `docs/agentic/work/<story>/design.md`
- `docs/agentic/work/<story>/plan.md`
- `docs/agentic/work/<story>/review.md`
- `docs/agentic/work/<story>/handoff.md`

## Parallélisme

Ne paralléliser que des stories indépendantes ou dont les contrats sont stabilisés.

L'orchestrateur doit :

- calculer les dépendances ;
- lancer d'abord les stories structurantes ;
- isoler les changements ;
- éviter les collisions de fichiers ;
- bloquer une vague si une dépendance structurante échoue.

## États

- BACKLOG
- PRD
- STORIES
- STORY_REVIEW
- ARCHITECTURE
- DESIGN_SYSTEM
- RESEARCH
- DESIGN
- PLANNED
- IMPLEMENTING
- REVIEW
- BLOCKED
- PR_OPEN
- CI
- READY_FOR_HUMAN
- DONE

## Sécurité et qualité

Tout projet doit expliciter dans PRD/Architecture/Research :

- authentification ;
- autorisation ;
- données sensibles ;
- isolation tenant si applicable ;
- secrets ;
- actions externes ;
- validation humaine pour les actions sensibles ;
- stratégie de tests ;
- observabilité et rollback lorsque pertinent.

## Modèles

Utiliser le modèle le moins coûteux capable de réaliser correctement la phase.

- PRD, architecture, sécurité, arbitrages, review critique : modèle puissant ;
- research/plan standards et implémentation bien cadrée : modèle intermédiaire ;
- documentation mécanique, tests répétitifs, mises à jour de statut : modèle économique ;
- escalader si blocage ou ambiguïté persistante.

Le choix du modèle ne remplace jamais les gates.
