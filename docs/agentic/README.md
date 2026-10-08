# Navigation de la méthode

Lire cet index après le README du projet. Charger les documents selon la phase
et le risque, sans charger tout le dépôt à chaque tour. Les règles activées par
un déclencheur restent obligatoires. Si la prochaine phase est inconnue, lire
METHOD, repérer le dernier PASS et reprendre la phase suivante.

| Déclencheur | Lecture obligatoire | Résultat attendu |
|---|---|---|
| Début de mission | [SCALING](SCALING.md), [WORKFLOW](WORKFLOW.md), [SAFETY](SAFETY.md) | entrée, risque, phase et limites |
| Première utilisation, phase ambiguë, architecture | [METHOD](METHOD.md) | pipeline et décisions applicables |
| Nouveau produit / gros périmètre | [BOOTSTRAP](BOOTSTRAP.md), documents de docs/product, ADR | cinq gates produit |
| Ticket sur existant | [EXISTING_PROJECT](EXISTING_PROJECT.md) | cadrage et socle observé |
| Installation / usage personnel | [INSTALL](INSTALL.md), [LOCAL](LOCAL.md) si LOCAL | activation explicite |
| Choix du niveau / délégation | [MODELS](MODELS.md), rôle concerné ci-dessous | capacité et contrat |
| Tâche longue, recherche, reprise | [CONTEXT](CONTEXT.md), [HANDOFF](templates/HANDOFF.md) | checkpoint vérifiable |
| Outil tiers envisagé | [OPTIONAL_TOOLS](OPTIONAL_TOOLS.md) | qualification avant activation |
| Story significative | [WORKTREE_ENVIRONMENT](templates/WORKTREE_ENVIRONMENT.md) | environnement reproductible |
| Tâche longue / complexe | [GOAL](templates/GOAL.md) | critères mesurables |
| Commit | [COMMITS](../../COMMITS.md) | Gitmoji et ticket |
| PR à livrer | [Profil Lead Tech](roles/REVIEWER.md), [Ship](templates/SHIP.md) | avis indépendant sur la révision finale |
| Suivi | [STATUS](STATUS.md) | état réel sans PASS fictif |

Pour chaque phase charger son template : [PRD](templates/PRD.md),
[Stories](templates/STORIES.md), [Story Review](templates/STORY_REVIEW.md),
[Architecture](templates/ARCHITECTURE.md), [ADR](templates/ADR.md),
[Design System](templates/DESIGN_SYSTEM.md), [Research](templates/RESEARCH.md),
[Design](templates/DESIGN.md), [Plan](templates/PLAN.md),
[Execute](templates/EXECUTE.md), [Verify](templates/VERIFY.md), [Review](templates/REVIEW.md),
[Ship](templates/SHIP.md). Artefacts de story dans `docs/agentic/work/<story>/` :
research, design, plan, handoff, verify, review ; goal si applicable.

Rôles : [orchestrator](roles/ORCHESTRATOR.md), [implementer](roles/IMPLEMENTER.md),
[reviewer](roles/REVIEWER.md). Les spécialisations sont des contrats de mission,
pas une collection d’agents toujours chargés.
