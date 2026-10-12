# Navigation de la méthode

Lire cet index après README. Charger uniquement les règles utiles à la phase et
au risque ; chaque déclencheur rend sa lecture obligatoire. Si la phase est
inconnue, lire METHOD, repérer le dernier PASS prouvé et reprendre la suite.

`PREPARE → BUILD → SHIP`

| Déclencheur | Lecture obligatoire | Résultat attendu |
|---|---|---|
| Début de mission | [SCALING](SCALING.md), [WORKFLOW](WORKFLOW.md), [SAFETY](SAFETY.md) | entrée, risque, phase, limites |
| Première utilisation / architecture | [METHOD](METHOD.md) | gates et décisions |
| Nouveau produit / gros périmètre | [BOOTSTRAP](BOOTSTRAP.md), docs/product disponibles, ADR | six rubriques adaptées |
| Ticket sur existant | [EXISTING_PROJECT](EXISTING_PROJECT.md) | décisions réutilisées, delta utile |
| PREPARE | [PREPARE](templates/PREPARE.md) | PRD, TRD, APP_FLOW, UX_UI_BRIEF, BACKEND_SCHEMA, IMPLEMENTATION_PLAN |
| Installation / usage personnel | [INSTALL](INSTALL.md), [LOCAL](LOCAL.md) si LOCAL | activation, protections et migration |
| Modèles / délégation | [MODELS](MODELS.md), rôles ci-dessous | capacités réelles, contrats et observations |
| Recherche / reprise / tâche longue | [CONTEXT](CONTEXT.md), [HANDOFF](templates/HANDOFF.md) | checkpoint local vérifiable |
| Outil tiers envisagé | [OPTIONAL_TOOLS](OPTIONAL_TOOLS.md) | choix et validations planifiées |
| BUILD non trivial / PR | [PULL_REQUESTS](PULL_REQUESTS.md), [PR_SPLIT](templates/PR_SPLIT.md) | split PASS avant BUILD, scope PASS avant SHIP |
| Environnement significatif / risqué | [WORKTREE_ENVIRONMENT](templates/WORKTREE_ENVIRONMENT.md) | ownership, ressources, reproductibilité |
| Tâche longue / complexe | [GOAL](templates/GOAL.md) | critères mesurables |
| Écriture / correction / refactoring | [DEVELOPMENT](DEVELOPMENT.md) | conventions, scope et tests |
| Commit | [COMMITS](../../COMMITS.md) | Gitmoji, ticket, garde staged |
| SHIP | [Profil Lead Tech](roles/REVIEWER.md), [Ship](templates/SHIP.md) | examen indépendant et preuves fraîches |
| Suivi | [STATUS](templates/STATUS.md) | état réel, aucun PASS fictif |

BUILD réutilise [Execute](templates/EXECUTE.md), [Verify](templates/VERIFY.md),
[Review](templates/REVIEW.md) pour les activités et preuves, à profondeur adaptée.
Les notes, handoffs et preuves personnels restent locaux, exclus de Git.
Les templates V1 PRD/Stories/Story Review/Architecture/Design System/Research/Design/
Plan restent conservés pour reprise/legacy et références ; facultatifs pour une
nouvelle mission V2, aucun PASS distinct exigé. [ADR](templates/ADR.md) trace les
décisions durables. Leur présence ne constitue pas un gate.

Rôles : [orchestrator](roles/ORCHESTRATOR.md), [implementer](roles/IMPLEMENTER.md),
[reviewer](roles/REVIEWER.md). Les spécialisations sont des contrats temporaires,
pas des agents automatiquement lancés. Les scripts `agentic-build.py`,
`agentic-workspace.py`, `agentic-skills.py`, `agentic-models.py`,
`agentic-scheduler.py`, `agentic-quality.py` sont utilisés si disponibles ; vérifier
leur présence/capacités. Le runtime hôte réalise la délégation native et conserve
ses reçus, sinon fallback honnête. Aucun lien de configuration native supposée.
