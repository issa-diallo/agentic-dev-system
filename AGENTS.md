# Agentic Project Rules

## Entrée et navigation

Lire README du projet puis [l’index de méthode](docs/agentic/README.md).
Choisir LIGHT, STANDARD ou LARGE via [SCALING](docs/agentic/SCALING.md) avant
le travail. Charger les règles détaillées dès que leur déclencheur s’applique :
un renvoi conditionnel ne rend aucune obligation facultative.
En cas de conflit entre documents projet, ordre de référence : README,
METHOD, WORKFLOW, COMMITS, docs/product disponibles, ADR applicables,
ticket, artefacts de story. Les instructions du système et de l’utilisateur priment.

## Pipeline et gates

Nouveau produit ou gros périmètre :
`PRD -> Stories -> Story Review -> Architecture -> Design System -> Research -> Design -> Plan -> Worktree Setup -> Execute -> Verify -> Review -> Goal -> Ship`.
Story cadrée : reprendre à Research. Projet existant sans documents produit :
appliquer [EXISTING_PROJECT](docs/agentic/EXISTING_PROJECT.md), consigner ticket,
socle observé et justification dans Research ; aucun PASS produit inventé.
Worktree Setup et Goal s’appliquent selon le risque et la durée.
Ne pas sauter, inverser ni oublier une phase sans justification explicite.
Chaque phase applicable produit un artefact et PASS ou BLOCKED ; la suivante
attend PASS. Review admet PASS_WITH_MINOR, jamais Critical/Major ouvert.

DoR Execute : critères clairs, dépendances connues, Research/Design/Plan PASS,
architecture/ADR compatibles, fichiers identifiés, tests définis, risques critiques
traités, aucun blocker. Sinon poursuivre la préparation.
Après Execute, Verify obligatoire : tests réellement exécutés et preuves adaptées
(build, API, navigateur, captures, logs, performances). Puis review indépendante.
DoD : Execute et Verify PASS, Review PASS/PASS_WITH_MINOR, Goal SATISFIED si
applicable, CI PASS, validation humaine si requise, merge et cleanup effectués.
Une mission limitée à une PR s’arrête à READY_FOR_HUMAN, jamais DONE.

## Invariants d’exécution

L’agent principal orchestre ; l’implementer ne peut être son seul reviewer.
Story non triviale : identifiant, branche et worktree dédiés, implementer,
reviewer indépendant et PR dédiée. Jamais deux écrivains dans le même worktree.
Paralléliser seulement des stories indépendantes ou à contrats stabilisés ;
calculer les dépendances, lancer les stories structurantes d’abord et bloquer
la vague si une dépendance structurante échoue.
Pour une story significative, environnement reproductible selon
[WORKTREE_ENVIRONMENT](docs/agentic/templates/WORKTREE_ENVIRONMENT.md).
Tâche longue/complexe : [CONTEXT](docs/agentic/CONTEXT.md) et goal mesurable
selon [GOAL](docs/agentic/templates/GOAL.md), jusqu’à SATISFIED ou blocker réel.

Stack décidée en Architecture ; socle observé suffit sans changement structurant
sur l’existant. Détails et ADR obligatoires dans [METHOD](docs/agentic/METHOD.md).
Changement de décision approuvée : BLOCKED, ADR et ARCHITECTURE mis à jour,
validation du choix, puis reprise. Aucun remplacement silencieux.

Lire et appliquer [SAFETY](docs/agentic/SAFETY.md) : secrets protégés, actions
sensibles validées, hooks si disponibles sans substituer les règles.
PRD/Architecture/Research explicitent auth, autorisation, données sensibles,
tenant si applicable, secrets, actions externes, validation humaine, tests,
observabilité et rollback pertinents.
Avant chaque commit, appliquer [COMMITS](COMMITS.md) : Gitmoji Unicode officiel
approprié, titre court impératif, pourquoi si nécessaire, intention atomique,
`Fixes #<issue_number>`.

Choisir le modèle le moins coûteux capable selon [MODELS](docs/agentic/MODELS.md),
escalader sur preuves ; jamais au prix d’un gate. États, artefacts et rôles sont
précisés par [WORKFLOW](docs/agentic/WORKFLOW.md) et l’index.
