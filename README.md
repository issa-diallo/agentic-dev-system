# Agentic Dev System

Un cadre à installer dans votre dépôt pour développer avec des agents IA (Codex,
Claude Code, tout harnais CLI) : cadrer une fonctionnalité, l'implémenter isolée,
la tester, la faire relire indépendamment et livrer une PR vérifiable. Il n'impose aucune stack.

## Démarrage rapide

Remplacer `~/mon-projet` par la racine du dépôt Git du projet. Prérequis : Bash, Git, Python 3.

**Installer**

```bash
git clone git@github.com:issa-diallo/agentic-dev-system.git ~/agentic-dev-system
~/agentic-dev-system/install-agentic.sh ~/mon-projet
```

L'installation pose la méthode dans `.agentic-local/` (exclu de Git), crée
`~/.codex/AGENTS.md` s'il n'existe pas et pose un hook Git `pre-push` local.
Relancer ensuite `codex` dans le projet.

**Mettre à jour un projet déjà installé**

```bash
git -C ~/agentic-dev-system pull
python3 ~/agentic-dev-system/update-agentic.py ~/mon-projet --dry-run   # voir ce qui change
python3 ~/agentic-dev-system/update-agentic.py ~/mon-projet
python3 ~/mon-projet/.agentic-local/scripts/agentic-pr-check.py install-guard --repo ~/mon-projet
```

**Remplacer le fichier global Codex** (jamais écrasé par l'installation)

```bash
cp ~/.codex/AGENTS.md ~/.codex/AGENTS.md.bak
cp ~/agentic-dev-system/codex/global-AGENTS.md ~/.codex/AGENTS.md
```

**Vérifier** : dans une session `codex` neuve, demander « Recopie mot pour mot, sans résumer, les règles globales agentic-dev-system que tu as reçues au démarrage. ».
Le titre « Méthode agentic-dev-system (global) » doit apparaître, avec la ligne sur
`pr-split.json` si le fichier est à jour. Demander quels fichiers sont chargés ne
prouve rien : Codex ne cite pas leur chemin.

Installation partagée (versionnée avec l'équipe), collisions et migration :
[INSTALL](docs/agentic/INSTALL.md). Usage personnel : [LOCAL](docs/agentic/LOCAL.md).

## Ce que ça garantit

- **Un travail cadré** : besoin, critères d'acceptation et plan avant le code.
- **Une capacité autonome par PR** : le gate PR_SPLIT découpe avant BUILD ; un hook
  `pre-push` refuse une branche sans plan valide ni fichiers hors périmètre.
- **Des changements isolés** : une branche et un worktree par PR non triviale.
- **Une review indépendante** : un reviewer distinct de l'auteur, puis un examen
  final [Lead Tech](docs/agentic/roles/REVIEWER.md) ; l'agent ne fusionne jamais sans votre accord.
- **Du code lisible** : [DEVELOPMENT](docs/agentic/DEVELOPMENT.md) (SOLID, DRY, KISS, YAGNI, nommage).
- **Une livraison traçable** : ticket, tests, commits Gitmoji ([COMMITS](COMMITS.md)) et PR reliés.

## Une méthode, trois échelles

| Mode | Usage | Profondeur |
|---|---|---|
| LIGHT | Petit projet, prototype, correction ciblée | Artefacts courts |
| STANDARD | Application web, développement courant | Préparation et preuves complètes |
| LARGE | Multi-applications, données sensibles, production critique | Contrats, isolation et validation renforcés |

Choisir selon le [risque](docs/agentic/SCALING.md). La profondeur change,
les gates de qualité restent obligatoires.

## Du besoin à la livraison

```text
PREPARE → BUILD → SHIP
```

- **PREPARE** : six rubriques (PRD, TRD, APP_FLOW, UX_UI_BRIEF, BACKEND_SCHEMA,
  IMPLEMENTATION_PLAN) dans un seul [fichier](docs/agentic/templates/PREPARE.md).
  Sur un [projet existant](docs/agentic/EXISTING_PROJECT.md), on réutilise les
  décisions validées, sans ajouter Research/Design/Plan à chaque tâche ; les
  templates V1 restent facultatifs pour la reprise.
- **BUILD** : PR_SPLIT PASS, un seul écrivain par worktree, Verify, review indépendante.
- **SHIP** : PR_SCOPE, preuves fraîches, examen final, CI, puis votre autorisation de fusion.

Aucun PASS n'est inventé ; les préparations, plans et rapports restent locaux, hors des commits.

## S'orienter

| Besoin | Référence |
|---|---|
| Trouver les instructions utiles | [Index de la méthode](docs/agentic/README.md) |
| Phases et gates | [Méthode](docs/agentic/METHOD.md), [workflow](docs/agentic/WORKFLOW.md) |
| Découpage en PR | [PULL_REQUESTS](docs/agentic/PULL_REQUESTS.md) |
| Modèles et délégation à un modèle économique | [MODELS](docs/agentic/MODELS.md), [DELEGATION](docs/agentic/DELEGATION.md) |
| Rôles | [Orchestrateur](docs/agentic/roles/ORCHESTRATOR.md), [implementer](docs/agentic/roles/IMPLEMENTER.md), [reviewer](docs/agentic/roles/REVIEWER.md) |
| Sécurité et outils optionnels | [Safety](docs/agentic/SAFETY.md), [outils optionnels](docs/agentic/OPTIONAL_TOOLS.md) |

Détails (isolation, relecture de PR, installation détaillée, héritage) : [OVERVIEW](docs/agentic/OVERVIEW.md).

## Vérifier et contribuer

```bash
(cd .agentic-local && bash scripts/agentic-check.sh --existing)   # dans un projet installé en local
python3 -m unittest discover -s tests -v                           # dans ce dépôt
```

Le premier contrôle vérifie la présence des ressources, pas le passage des gates.
