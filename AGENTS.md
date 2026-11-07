# Agentic Project Rules

## Entrée et navigation

Lire README et [l’index de méthode](docs/agentic/README.md). Choisir LIGHT/STANDARD/LARGE
via [SCALING](docs/agentic/SCALING.md). Charger les règles déclenchées, toujours obligatoires.
Ordre projet : README, METHOD, WORKFLOW, COMMITS, docs/product, ADR applicables, ticket,
artefacts de mission. Système et utilisateur priment.

## Pipeline et gates

`PREPARE → BUILD → SHIP`
PREPARE : six rubriques PRD, TRD, APP_FLOW, UX_UI_BRIEF, BACKEND_SCHEMA, IMPLEMENTATION_PLAN ;
un fichier/références suffit. LIGHT minimal, STANDARD concis, LARGE structuré. Sur existant,
réutiliser les décisions et compléter le delta ([EXISTING_PROJECT](docs/agentic/EXISTING_PROJECT.md)).
Templates V1 conservés pour reprise/legacy ; présence d'un fichier ne vaut jamais PASS.
Phase applicable : artefact et PASS/BLOCKED ; seule PASS autorise la suite.

DoR BUILD : AC clairs, dépendances connues, PREPARE PASS, PR_SPLIT PASS pour BUILD non
trivial, architecture/ADR compatibles, fichiers identifiés, tests définis, risques critiques
traités, aucun blocker. Verify obligatoire après Execute : tests exécutés et preuves adaptées.
Puis review indépendante PASS/PASS_WITH_MINOR, jamais Critical/Major ouvert. Profil Lead
Tech : review finale LIGHT/STANDARD ; seconde lecture distincte LARGE/risque critique.
DoD : PR_SPLIT/PR_SCOPE PASS, Verify PASS, Review PASS/PASS_WITH_MINOR, Goal SATISFIED si
applicable, CI PASS, validation humaine si requise, autorisation de merge, merge et cleanup.
Mission limitée à une PR : READY_FOR_HUMAN ; états dans [WORKFLOW](docs/agentic/WORKFLOW.md).

## Invariants d’exécution

L'agent principal orchestre ; l'implementer ne peut être son seul reviewer. PR non triviale :
identifiant, branche/worktree, owner unique, implementer et reviewer indépendant. Jamais deux
écrivains dans un worktree. PR_SPLIT avant BUILD ([PULL_REQUESTS](docs/agentic/PULL_REQUESTS.md)),
DAG/ressources calculés, PR structurantes d'abord, parallélisme seulement entre unités
indépendantes ; descendants bloqués si une dépendance structurante échoue. Environnement :
[WORKTREE_ENVIRONMENT](docs/agentic/templates/WORKTREE_ENVIRONMENT.md).

Router skills/modèles disponibles, lancer réellement les sous-agents (reçus, arrêt confirmé,
handoff vérifié) ; sinon repli séquentiel explicite et review en session indépendante.
Aucune délégation, aucun modèle ni métrique inventés ; coûts non observés : null. Délégation
économique : [DELEGATION](docs/agentic/DELEGATION.md). Tâche longue : [CONTEXT](docs/agentic/CONTEXT.md),
checkpoint local et [GOAL](docs/agentic/templates/GOAL.md) mesurable.

Architecture courte, choix utilisateur conservés ; validations différées avec responsable et
échéance. Fait nouveau invalidant une contrainte : stories affectées
BLOCKED, ADR et ARCHITECTURE mis à jour puis validation ([METHOD](docs/agentic/METHOD.md)).

[SAFETY](docs/agentic/SAFETY.md) : secrets protégés, actions sensibles validées. PREPARE traite
auth, autorisation, tenant, données sensibles, secrets, actions externes, tests, observabilité
et rollback selon risque. Code : [DEVELOPMENT](docs/agentic/DEVELOPMENT.md). Commits :
[COMMITS](COMMITS.md), Gitmoji, `Fixes #<issue_number>`, garde `agentic-commit.sh`. Préparation
et rapports hors Git/PR. Modèle le moins coûteux capable ([MODELS](docs/agentic/MODELS.md)),
escalade sur preuves, jamais au prix d'un gate. SHIP : profil Lead Tech de
[REVIEWER](docs/agentic/roles/REVIEWER.md).

## Communication commune à tous les agents

Commencer par le résultat ou la réponse principale. Phrases courtes, précises, directes ;
ne pas recopier code, logs ou fichiers accessibles ; résumer les changements avec leurs
chemins ; pour les tests, statut et erreurs pertinentes ; signaler
blocages, risques, incertitudes et validations manquantes ; ne pas détailler les étapes internes.

Format par défaut, sections vides omises :

- **Résultat :** terminé, partiel ou bloqué, puis réponse principale.
- **Modifications :** changements essentiels et chemins.
- **Validation :** tests exécutés, résultats ; tests non exécutés signalés.
- **Attention :** risques ou décisions nécessaires, seulement si présents.
- **Prochaine étape :** seulement si une action reste.

Instructions prioritaires et formats spécifiques PREPARE → SHIP priment sur ce format.
Exactitude, sécurité, qualité et complétude ne sont jamais réduites pour économiser des
tokens ; rapports techniques et métier restent complets ([CONTEXT](docs/agentic/CONTEXT.md)).
