# Agentic Project Rules

## Entrée et navigation

Lire README et [l’index de méthode](docs/agentic/README.md).
Choisir LIGHT/STANDARD/LARGE via [SCALING](docs/agentic/SCALING.md).
Charger les règles déclenchées, toujours obligatoires. Ordre projet : README, METHOD, WORKFLOW,
COMMITS, docs/product disponibles, ADR applicables, ticket, artefacts de mission.
Système et utilisateur priment.

## Pipeline et gates

`PREPARE → BUILD → SHIP`
PREPARE : six rubriques PRD, TRD, APP_FLOW, UX_UI_BRIEF, BACKEND_SCHEMA,
IMPLEMENTATION_PLAN ; un fichier/références suffit. LIGHT minimal, STANDARD concis,
LARGE structuré. Sur existant, réutiliser décisions/artefacts et compléter le delta
selon [EXISTING_PROJECT](docs/agentic/EXISTING_PROJECT.md), sans Research/Design/Plan
supplémentaires par tâche. Conserver templates et données V1 pour reprise/legacy,
sans PASS produit inventé ; présence d'un fichier ne vaut jamais PASS.
Phase applicable : artefact et PASS/BLOCKED ; seule PASS autorise la suite.

DoR BUILD : AC clairs, dépendances connues, PREPARE PASS, PR_SPLIT PASS pour BUILD
non trivial, architecture/ADR compatibles, fichiers identifiés, tests définis,
risques critiques traités, aucun blocker.
Verify obligatoire après Execute : tests exécutés et preuves adaptées
(build, API, navigateur, captures, logs, performances). Puis review indépendante.
Review PASS/PASS_WITH_MINOR, jamais Critical/Major ouvert. Profil Lead Tech : review
indépendante finale LIGHT/STANDARD ; seconde lecture distincte LARGE/risque critique.
DoD : PR_SCOPE PASS, Execute/Verify PASS, Review PASS/PASS_WITH_MINOR, Goal
SATISFIED si applicable, CI PASS, validation humaine si requise, autorisation de
merge, merge et cleanup effectués. Mission limitée à une PR : READY_FOR_HUMAN ; états dans [WORKFLOW](docs/agentic/WORKFLOW.md).

## Invariants d’exécution

L'agent principal orchestre ; l'implementer ne peut être son seul reviewer.
PR autonome ; non triviale : identifiant, branche/worktree, owner
unique, implementer et reviewer indépendant. Jamais deux écrivains dans un worktree.
PR_SPLIT avant BUILD non trivial selon [PULL_REQUESTS](docs/agentic/PULL_REQUESTS.md).
Calculer DAG/ressources, lancer les PR structurantes d'abord, paralléliser seulement
unités indépendantes ou contrats stabilisés ; bloquer les descendants si une
dépendance structurante échoue. Environnement reproductible selon risque via
[WORKTREE_ENVIRONMENT](docs/agentic/templates/WORKTREE_ENVIRONMENT.md).

Router skills/modèles disponibles, charger les skills et lancer réellement les
sous-agents natifs ; garder identifiants observés, arrêt confirmé et handoff vérifié. Fallback
séquentiel explicite si indisponible, review en session indépendante ; aucune
délégation, modèle principal ou métrique inventés. Coûts non observés : null.
Tâche longue/complexe : [CONTEXT](docs/agentic/CONTEXT.md), checkpoint local et
[GOAL](docs/agentic/templates/GOAL.md) mesurable jusqu'à SATISFIED ou blocker réel.

Architecture courte, choix utilisateur conservés sans qualification systématique.
Validations différées avec responsable/échéance, preuves en BUILD/Verify ; coûts
après implémentation. Fait nouveau invalidant une contrainte : seules stories
affectées BLOCKED, ADR et ARCHITECTURE mis à jour puis validation ; autorisation
existante suffit, aucun remplacement silencieux. [METHOD](docs/agentic/METHOD.md).

[SAFETY](docs/agentic/SAFETY.md) : secrets protégés, actions sensibles validées,
hooks si disponibles sans remplacer les règles. PREPARE traite auth, autorisation,
tenant, données sensibles, secrets, actions externes, validation humaine, tests,
observabilité et rollback selon risque. Code : [DEVELOPMENT](docs/agentic/DEVELOPMENT.md).
Avant commit : [COMMITS](COMMITS.md), Gitmoji Unicode, titre impératif, intention
atomique, `Fixes #<issue_number>`, garde staged via `agentic-commit.sh`.
Préparation et rapports hors Git/PR. Modèle le moins coûteux
capable selon [MODELS](docs/agentic/MODELS.md), escalader sur preuves, jamais au
prix d'un gate. SHIP applique le profil Lead Tech de [REVIEWER](docs/agentic/roles/REVIEWER.md).

## Communication commune à tous les agents

Commencer par le résultat ou la réponse principale. Phrases courtes, précises,
directes ; sans introduction inutile, répétition ni conclusion redondante.
Résumer les changements avec leurs chemins ; ne pas recopier code, logs ou
fichiers accessibles. Pour les tests : statut et erreurs pertinentes. Signaler
blocages, risques, incertitudes et validations manquantes. Ne pas détailler
les étapes internes quand le résultat suffit.

Format par défaut, sections vides omises :

- **Résultat :** terminé, partiel ou bloqué, puis réponse principale.
- **Modifications :** changements essentiels et chemins.
- **Validation :** tests exécutés, résultats ; tests non exécutés signalés.
- **Attention :** risques ou décisions nécessaires, seulement si présents.
- **Prochaine étape :** seulement si une action reste.

Instructions prioritaires et formats spécifiques PREPARE → SHIP priment sur ce
format conversationnel. Exactitude, sécurité, qualité et complétude des livrables
ne sont jamais réduites pour économiser des tokens ; rapports techniques et
métier restent complets. Voir [CONTEXT](docs/agentic/CONTEXT.md) pour la portée.
