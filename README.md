# Agentic Dev System

Un cadre de travail à installer dans votre dépôt pour développer avec des agents
IA : cadrer une fonctionnalité, isoler son implémentation, la tester, la faire
relire indépendamment et préparer une Pull Request vérifiable.

Il fournit les instructions et les modèles de documents qui organisent ce cycle
avec Codex, sans imposer la stack de votre application.

## À quoi ça sert pour un développeur ?

Quand vous confiez une fonctionnalité à un agent, vous voulez savoir ce qu'il va
modifier, éviter qu'il perturbe les autres travaux et vérifier son résultat avant
la fusion. Le système définit les règles pour obtenir :

- **Un travail cadré** : besoin, critères d'acceptation et plan avant l'implémentation.
- **Des changements isolés** : branche et worktree dédiés par story non triviale,
  pour séparer les fichiers de travail des autres fonctionnalités.
- **Un environnement reproductible** : commandes de préparation, démarrage,
  test et arrêt définies pour le projet.
- **Une validation indépendante** : un reviewer distinct de l'auteur confronte
  le diff aux critères et aux preuves de test.
- **Une livraison traçable** : ticket, décisions, tests, commits et PR reliés.

Par exemple, pour ajouter un export CSV : vous décrivez le besoin ; l'agent
précise les critères et le plan ; l'implémentation se fait dans un worktree dédié ;
les tests vérifient le résultat ; un autre agent effectue la review ; un agent
Lead Tech examine la PR et vous remet un avis technique avant votre décision de fusion. Les étapes et preuves restent dans le dépôt.

## Qui examine la PR avant la fusion ?

Le [Lead Tech](docs/agentic/roles/REVIEWER.md) réalise une synthèse indépendante :
architecture, risques, preuves de test, CI et préparation à la livraison. Son rapport
indique le verdict, les problèmes concrets, les corrections et les incertitudes.

Sur une PR STANDARD/LARGE, c'est un second agent distinct de l'implementer et du
premier reviewer. Sur une petite PR LIGHT, le reviewer indépendant peut remplir
cette mission directement. Le modèle doit être performant et disponible, avec
raisonnement High ou Extra High selon le risque ; aucun nom de modèle n'est imposé.

L'orchestrateur lui transmet le diff et les preuves pour un commit précis, puis
fait corriger les problèmes et demande une revalidation. Un problème bloquant ou
une CI non validée empêche la livraison. Un nouveau commit impose un avis actualisé.
Vous recevez une recommandation technique argumentée ; l'agent ne fusionne pas
sans autorisation. Le contrat et le prompt sont fournis dans le rôle Reviewer,
sans bot GitHub installé automatiquement.

## Comment l'isolation fonctionne-t-elle ?

| Ce qui doit être séparé | Mécanisme prévu par la méthode |
|---|---|
| Code de deux fonctionnalités | Une branche et un worktree Git par story non triviale ; un seul agent écrit dans chaque worktree |
| Services et données d'exécution | Ports, bases ou schémas, queues et ressources propres au worktree lorsque le projet en a besoin |
| Implémentation et contrôle | Un reviewer indépendant, avec accès au diff et aux résultats de validation |

Un worktree isole les fichiers de travail ; il n'isole pas à lui seul une base de
données ou un service partagé. Dev, test et review sont les activités du cycle :
elles ne nécessitent pas systématiquement trois environnements distincts.
Leur organisation dépend du projet et des risques.

**L'installation ajoute la méthode au dépôt.** Elle ne crée pas automatiquement
les worktrees, conteneurs, bases de données ou environnements de preview.
L'agent prépare les worktrees pendant l'exécution des stories ; les scripts
`worktree-setup.sh`, `worktree-dev.sh`, `worktree-test.sh` et `worktree-down.sh`
sont à fournir dans `scripts/` lorsque le projet en a besoin, selon le
[contrat d'environnement](docs/agentic/templates/WORKTREE_ENVIRONMENT.md).
Les agents et leur orchestration s'appuient sur les capacités de votre outil.

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
- **Code lisible et PR courtes** : [DEVELOPMENT](docs/agentic/DEVELOPMENT.md)
  fixe les conventions SOLID, noms et modules ;
  [PULL_REQUESTS](docs/agentic/PULL_REQUESTS.md) vise un objectif,
  un commit final et 1 à 3 fichiers par PR, sans supprimer les tests.
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
