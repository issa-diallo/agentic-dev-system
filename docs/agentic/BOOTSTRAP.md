# Bootstrap — démarrer une mission

Installer le socle avec `install-agentic.sh` selon [INSTALL](INSTALL.md) et activer
explicitement le mode personnel selon [LOCAL](LOCAL.md). Lire README, index,
SCALING et SAFETY. Identifier PRODUCT/EXISTING et les capacités runtime réellement exposées.

## PREPARE

Utiliser [PREPARE](templates/PREPARE.md) : six rubriques PRD, TRD, APP_FLOW,
UX_UI_BRIEF, BACKEND_SCHEMA, IMPLEMENTATION_PLAN. LIGHT minimal, STANDARD concis,
LARGE structuré. Aucun six gros fichiers ni dossier Research/Design/Plan par tâche.
Référencer les décisions utilisateur et artefacts existants ; N/A motivés.
Conserver toute préparation, y compris collective ou approuvée, dans
`.agentic-local/docs/agentic/work/<ticket>/`, exclu de Git. Les documents existants
restent consultables ; ne pas ajouter de plan ou rapport dans une PR applicative.

L'installation PRODUCT distribue encore cinq templates produit V1 pour transition.
Ils restent facultatifs pour une nouvelle mission V2, utilisables pour reprise/legacy.
Ne pas supprimer les données/décisions V1, remplir artificiellement les templates
ou interpréter leur présence comme PASS. EXISTING réutilise le socle observé selon
[EXISTING_PROJECT](EXISTING_PROJECT.md).

## Prompt de démarrage

> Lis README, AGENTS.md et docs/agentic/README.md. Choisis le mode selon le risque.
> Applique PREPARE → BUILD → SHIP : six rubriques adaptées, décisions réutilisées,
> PR_SPLIT avant BUILD non trivial, worktree et owner unique, délégation réellement
> lancée avec outils disponibles ou fallback honnête. Verify et review indépendante,
> PR_SCOPE, CI et autorisation avant merge. N'invente aucun PASS ni modèle utilisé.

## BUILD puis SHIP

Identifier les capacités et passer PR_SPLIT ; préparer les unités par dépendances,
branche/worktree, ownership, ressources et environnement reproductible selon besoin.
Vérifier les scripts V2 disponibles avant de les utiliser ; un fichier de rôle
n'est pas un agent lancé. Vérifier lancement/arrêt/handoff et preuves de qualité.
Conserver la review indépendante, l'examen final Lead Tech et les autorisations.

Checklist : socle complet, PREPARE PASS, PR_SPLIT PASS pour non trivial, isolation
et owner prêts, tests définis/réellement exécutés, review indépendante fraîche,
PR_SCOPE PASS, CI PASS, autorisation de merge. Sans merge/cleanup : pas de DONE.
Le contrôle `agentic-check.sh` teste les ressources, jamais les gates.
