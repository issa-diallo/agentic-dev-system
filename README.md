# Agentic Dev System

Une méthode réutilisable pour préparer, exécuter et vérifier le développement
avec Codex et des agents spécialisés. Elle fournit des instructions, des rôles,
des templates et un installateur, sans imposer de stack technique.

**Préparer clairement, charger le contexte utile et livrer avec des preuves.**

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
PRD → Stories → Story Review → Architecture → Design System
 ↓
Research → Design → Plan → Worktree Setup → Execute
 ↓
Verify → Review → Goal → Ship
```

Worktree Setup est requis pour les stories significatives ; Goal pour les tâches
longues ou complexes. Chaque phase applicable exige son artefact et son verdict.
Execute attend Research, Design et Plan PASS. Verify apporte les preuves,
puis un reviewer indépendant examine le résultat. Une PR prête à examiner
reste READY_FOR_HUMAN ; DONE exige aussi merge et cleanup.

Pour un ticket cadré sur un [projet existant](docs/agentic/EXISTING_PROJECT.md),
commencer à Research avec l’architecture observée, sans recréer artificiellement
les cinq documents produit. Un nouveau produit ou gros périmètre suit le cycle
complet. La stack est choisie en Architecture et les décisions structurantes
sont documentées par ADR.

## Installer dans un projet

Prérequis : Bash, un dossier cible existant et Git pour le clonage et le mode LOCAL.

```bash
git clone git@github.com:issa-diallo/agentic-dev-system.git
```

| Installation | Commande depuis le dossier contenant le clone | Effet |
|---|---|---|
| Nouveau produit | `./agentic-dev-system/install-agentic.sh /chemin/du/projet` | Socle et cinq templates produit |
| Projet existant, méthode partagée | `./agentic-dev-system/install-agentic.sh --existing /chemin/du/projet` | Socle sans documents produit |
| Usage personnel dans un dépôt d’équipe | `./agentic-dev-system/install-agentic.sh --local /chemin/du/projet` | Socle dans `.agentic-local/`, exclu de Git |

LOCAL exige la racine d’un dépôt Git, préserve les fichiers de l’équipe et
nécessite une [activation explicite](docs/agentic/LOCAL.md). Les règles de
l’équipe restent prioritaires. Les collisions sont refusées ; aucune mise à jour
ne force l’écrasement des personnalisations. Voir [INSTALL](docs/agentic/INSTALL.md)
pour les protections, mises à jour et diagnostics.

Après installation partagée, demander à l’agent :

> Lis AGENTS.md et docs/agentic/README.md. Choisis le mode selon le risque,
> identifie le point d’entrée et la première phase non validée, puis applique
> ses gates. Ne change pas silencieusement la stack.

## Ce que chaque projet hérite

- **Instructions ciblées** : invariants dans `AGENTS.md`, navigation conditionnelle
  vers les documents nécessaires à la tâche.
- **Choix des modèles** : niveau adapté au travail, du plus léger capable aux
  niveaux exigeants justifiés ; aucun nom de modèle imposé.
- **Délégation cadrée** : objectif, fichiers, contraintes, critères, validations
  et livrable explicites ; pas de multiplication d’agents pour une tâche simple.
- **Contexte maîtrisé** : recherche ciblée et checkpoints conservant décisions,
  erreurs ouvertes, preuves et prochaines actions.
- **Communication concise native** : résultat en tête, changements avec chemins,
  statut des tests et risques explicites. Aucun outil Caveman ou I Have ADHD installé.
- **Qualité préservée** : DoR/DoD, Verify, revue indépendante, sécurité et commits
  Gitmoji liés à un ticket. Les rapports métier et techniques restent complets ;
  les formats propres aux phases priment sur le format conversationnel.

L’installateur copie ce socle automatiquement : pas de réglage Codex global ni
de dépendance tierce ajoutés. STATUS part d’un template neutre ; les preuves des
stories du dépôt source ne sont pas distribuées. Les installations existantes
se mettent à jour par comparaison et sauvegarde, pas par synchronisation automatique.
Personnaliser les documents projet et les `AGENTS.md` des sous-applications en
conservant les invariants communs.

## S’orienter

| Besoin | Référence |
|---|---|
| Trouver les instructions utiles | [Index de la méthode](docs/agentic/README.md) |
| Comprendre les phases et gates | [Méthode](docs/agentic/METHOD.md) et [workflow](docs/agentic/WORKFLOW.md) |
| Choisir le niveau et gérer un modèle indisponible | [Politique de modèles](docs/agentic/MODELS.md) |
| Recherche, concision, reprise et mesures | [Gestion du contexte](docs/agentic/CONTEXT.md) |
| Répartir et vérifier le travail | [Orchestrateur](docs/agentic/roles/ORCHESTRATOR.md), [implementer](docs/agentic/roles/IMPLEMENTER.md), [reviewer](docs/agentic/roles/REVIEWER.md) |
| Évaluer RTK, QMD, Headroom ou Ponytail | [Outils optionnels](docs/agentic/OPTIONAL_TOOLS.md) |
| Sécurité et historique Git | [Safety](docs/agentic/SAFETY.md) et [conventions Gitmoji](COMMITS.md) |

Les outils complémentaires sont évalués, jamais installés par défaut. Aucune
économie de tokens ou de quota n’est garantie : distinguer tailles mesurées,
comportement observé et métriques indisponibles.

## Vérifier

Dans un projet installé en PRODUCT :

```bash
bash scripts/agentic-check.sh
```

Pour EXISTING, ajouter `--existing`. En LOCAL :

```bash
(cd .agentic-local && bash scripts/agentic-check.sh --existing)
```

Ce contrôle vérifie la présence des ressources, pas le passage des gates.

Pour contribuer à ce dépôt, Python 3 permet d’exécuter les tests sans package externe :

```bash
bash -n install-agentic.sh scripts/agentic-check.sh
python3 -m unittest discover -s tests -v
git diff --check
```

La CI vérifie syntaxe et tests : installations PRODUCT/EXISTING/LOCAL, héritage,
liens locaux, règles critiques, personnalisation et protections Git. Ces tests
ne garantissent pas le comportement de chaque modèle.
