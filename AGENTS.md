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
4. `COMMITS.md`
5. les documents projet dans `docs/product/`
6. les ADR applicables dans `docs/adr/`
7. le ticket/story concerné
8. les artefacts de travail de la story

## Project scale

Avant de commencer, lire `docs/agentic/SCALING.md` et choisir :

- LIGHT
- STANDARD
- LARGE

Le pipeline reste le même. Seule la profondeur des artefacts change.

Objectif : préparer suffisamment pour réduire le temps d'implémentation,
sans imposer une bureaucratie disproportionnée aux petits projets.

## Definition of Ready for Execute

Une story ne peut entrer en Execute que si :

- critères d'acceptation clairs ;
- dépendances identifiées ;
- Research PASS ;
- Design PASS ;
- Plan PASS ;
- architecture/ADR compatibles ;
- fichiers/zones impactées identifiés ;
- stratégie de tests définie ;
- risques critiques traités ;
- aucun blocker ouvert.

Si ces conditions ne sont pas réunies, continuer la préparation au lieu de coder.

## Verify / Evidence

Après Execute, l'agent doit passer par Verify.

Règle : **ne pas dire que cela fonctionne, le prouver**.

Utiliser `docs/agentic/templates/VERIFY.md` et joindre selon le projet :

- tests ;
- build ;
- appels API ;
- browser flow ;
- screenshots ;
- logs ;
- mesures de performance.

## Goals

Pour les tâches longues ou complexes, utiliser
`docs/agentic/templates/GOAL.md`.

Un goal doit être mesurable et basé sur des preuves. L'agent ne s'arrête que
si les critères sont SATISFIED ou si un blocker réel est documenté.

## Worktree environments

Pour les stories significatives, le worktree doit être reproductible.

Référence : `docs/agentic/templates/WORKTREE_ENVIRONMENT.md`.

Quand le projet en a besoin, fournir :

- `scripts/worktree-setup.sh`
- `scripts/worktree-dev.sh`
- `scripts/worktree-test.sh`
- `scripts/worktree-down.sh`

## Context hygiene

Avant les longues tâches, appliquer `docs/agentic/CONTEXT.md`.

Le main agent conserve les décisions et contraintes. Les explorations lourdes
sont déléguées à des sub-agents qui renvoient des résumés exploitables.

## Safety

Lire `docs/agentic/SAFETY.md`.

Quand le harness le permet, utiliser des hooks pour bloquer ou contrôler les
actions destructrices. Les hooks restent une couche de sécurité, pas un
substitut aux règles de projet.

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
9. Worktree Setup si requis
10. Execute
11. Verify
12. Review
13. Goal si applicable
14. Ship

## Règle fondamentale

L'agent principal orchestre. Il ne doit pas coder par réflexe.

L'agent qui implémente ne doit pas être le seul reviewer de son propre travail.

## Architecture et stack technique

La stack technique est décidée pendant la phase `Architecture`, jamais au hasard pendant `Execute`.

`docs/product/ARCHITECTURE.md` doit expliciter au minimum :

- contraintes et besoins ayant influencé le choix ;
- options envisagées ;
- stack retenue ;
- raisons du choix ;
- alternatives rejetées ;
- conséquences et compromis ;
- décisions nécessitant un ADR.

Pour chaque décision structurante importante, créer un ADR dans `docs/adr/`
à partir de `docs/agentic/templates/ADR.md`.

Exemples de décisions pouvant nécessiter un ADR :

- framework frontend ;
- langage/framework backend ;
- base de données ;
- ORM ;
- protocole ou style d'API ;
- authentification ;
- autorisation ;
- stratégie multi-tenant ;
- système de queues/jobs ;
- stockage de fichiers ;
- hébergement ;
- observabilité ;
- CI/CD ;
- dépendance externe structurante.

Un agent en phase `Research`, `Design`, `Plan` ou `Execute` ne doit pas
remplacer silencieusement une décision de stack déjà approuvée.

Si une décision doit changer :

1. marquer la story BLOCKED ;
2. créer ou mettre à jour l'ADR concerné ;
3. mettre à jour `ARCHITECTURE.md` ;
4. faire valider le nouveau choix ;
5. seulement ensuite reprendre la story.

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

## Commits

Avant tout commit, lire et appliquer `COMMITS.md`.

Chaque commit doit :

- utiliser le **Gitmoji approprié** à l'intention principale du changement ;
- utiliser l'emoji Unicode officiel de https://gitmoji.dev/ ;
- avoir un titre court à l'impératif ;
- expliquer le pourquoi dans le corps lorsque nécessaire ;
- référencer le ticket associé avec `Fixes #<issue_number>` ;
- rester atomique et limité à une intention principale.

Format attendu :

```text
<gitmoji> <Imperative title>

<Why this change was needed>
<What changed at a high level>
<Any important consequence>

Fixes #<issue_number>
```

Exemples :

```text
✨ Add artisan assignment workflow
🐛 Fix tenant filter on conversations
♻️ Refactor email parsing service
✅ Add tests for claim routing
📝 Document deployment workflow
🔒️ Fix cross-tenant access check
🏗️ Separate domain and integration layers
```

Ne jamais choisir un Gitmoji décoratif ou arbitraire. Si l'intention du
commit est ambiguë, consulter `COMMITS.md` et https://gitmoji.dev/ avant de
committer.

## Artefacts attendus

### Produit
- `docs/product/PRD.md`
- `docs/product/STORIES.md`
- `docs/product/STORY_REVIEW.md`
- `docs/product/ARCHITECTURE.md`
- `docs/product/DESIGN_SYSTEM.md`
- `docs/adr/*.md` pour les décisions structurantes

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
