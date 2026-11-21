# Agentic Dev System

**Framework de développement agentique pour Codex, Claude Code et les CLI compatibles.**

Cadrer une demande, découper le travail, déléguer l'implémentation, vérifier les preuves, faire relire indépendamment et préparer une pull request contrôlée. **Aucune stack applicative imposée.** La méthode est installable projet par projet ; elle ne démarre pas de service autonome.

> **Principe :** les contrôles de qualité sont le socle ; l'automatisation avancée est activée volontairement, selon le projet et le risque. Installer des fichiers ou déclarer un agent ne prouve pas qu'un agent a réellement été exécuté.

**Navigation** — [Démarrage rapide](#démarrage-rapide) · [Fonctionnement](#fonctionnement) · [Modules et valeurs par défaut](#modules-et-valeurs-par-défaut) · [Configuration par projet](#configuration-par-projet) · [Commandes](#commandes-et-diagnostic) · [Documentation](#documentation-de-référence)

## Démarrage rapide

**Prérequis :** Bash, Git, Python 3 et un client CLI compatible installé et authentifié pour exécuter des missions. L'installation **LOCAL** est le comportement par défaut ; elle ne remplace pas les règles de votre équipe.

~~~bash
git clone git@github.com:issa-diallo/agentic-dev-system.git ~/agentic-dev-system
~/agentic-dev-system/install-agentic.sh ~/mon-projet
~~~

Remplacer `~/mon-projet` par la racine Git du projet cible. L'installation place la méthode dans `.agentic-local/` (exclu de Git), installe les profils natifs `.codex/agents/` et `.claude/agents/` avec exclusions ciblées, et tente d'installer un hook local `pre-push`. Un hook existant ou `core.hooksPath` n'est **jamais écrasé**. Si `~/.codex/AGENTS.md` n'existe pas, il est créé ; s'il existe, le vérifier manuellement. Voir [LOCAL](docs/agentic/LOCAL.md) et [INSTALL](docs/agentic/INSTALL.md).

Ouvrir une **nouvelle** session Codex dans le projet, puis demander :

~~~text
agentic ?
~~~

- **« Agentic Dev System prêt à commencer. »** : les contrôles de disponibilité de la méthode demandés par cette commande sont satisfaits.
- **« NON prêt : … »** : suivre la cause indiquée (`.agentic-local/`, hook ou instructions globales).
- Toute autre réponse : vérifier `~/.codex/AGENTS.md`, puis relancer une session. Ne pas supposer que `codex` charge automatiquement le contenu local sans ces instructions.

Ce diagnostic ne lance **ni** onboarding **ni** agent, et ne certifie **ni** l'authentification aux modèles, **ni** leur capacité.

### Première mission

Au premier **développement** (pas lors d'une simple lecture ou du diagnostic), l'[onboarding](docs/agentic/ONBOARDING.md) doit proposer de vérifier Codex, d'ajouter éventuellement Claude Code, puis de choisir explicitement les revues correctives et leurs limites. Un choix ou un test échoué **ne vaut pas activation**. Les paramètres sont enregistrés localement par projet, après vérifications.

Pour traiter un ticket dans une session qui a chargé la méthode :

~~~text
$start-ticket https://github.com/organisation/depot/issues/123
~~~

Cette forme suppose le skill installé dans les skills personnels Codex. Sinon, demander à l'agent de **lire** `.agentic-local/skills/start-ticket/SKILL.md` puis de traiter l'URL. [Voir le skill](skills/start-ticket/SKILL.md).

**Résultat visé :** une PR préparée avec preuves, arrêt possible en `BLOCKED` ou `READY_FOR_HUMAN`. **Aucune fusion automatique :** la validation humaine requise reste obligatoire.

## Fonctionnement

~~~text
Ticket / besoin
      |
      v
PREPARE ──> BUILD ──> SHIP ──> READY_FOR_HUMAN
  cadrage      code       preuves    validation humaine
  PR_SPLIT     Verify     PR_SCOPE   avant fusion
               Review     CI
~~~

| Phase | Responsabilité | Condition importante |
|---|---|---|
| **PREPARE** | Réutiliser le contexte du produit et clarifier critères d'acceptation, risques, plan et découpage des PR | `PR_SPLIT PASS` avant une implémentation non triviale |
| **BUILD** | Implémentation isolée, tests, `Verify`, revue **indépendante** de l'auteur | Fin de processus ≠ validation ; défaut `Major/Critical` bloquant |
| **SHIP** | Contrôler scope, SHA et preuves fraîches, Lead Tech selon risque, CI et checklist du ticket | Fusion **uniquement** après autorisation applicable |

En PREPARE, les modèles V1 restent disponibles pour reprendre un travail existant. Pour une nouvelle mission, les documents Research/Design/Plan sont facultatifs et peuvent alimenter les six rubriques de préparation.

Les livrables temporaires (briefs, plans, preuves, handoffs) restent hors des PR applicatives. Une PR vise une capacité autonome, avec worktree/owner séparé pour les changements non triviaux.

### Trois échelles, un socle de qualité

| Échelle | Usage | Différence |
|---|---|---|
| **LIGHT** | Documentation, petite correction | Préparation courte, contrôles adaptés |
| **STANDARD** | Développement applicatif courant | Préparation et preuves complètes |
| **LARGE** | Données sensibles, sécurité, migrations, production critique | Isolation, contrôles et lecture indépendante renforcés |

Ce sont des **niveaux de méthode selon le risque**, **pas** des interrupteurs qui activent les modules facultatifs. La revue indépendante, `Verify`, la CI et l'autorisation de fusion restent les exigences du workflow. Voir [SCALING](docs/agentic/SCALING.md).

## Modules et valeurs par défaut

**Comment lire ce tableau :**

- **Socle obligatoire** : exigé par la méthode sur les missions applicables ; l'exécution réelle dépend du CLI, des preuves et de l'environnement.
- **OFF dans le template** : désactivé ou absent du [fichier de configuration d'exemple](docs/agentic/templates/agentic.config.json). Ce n'est **pas** nécessairement l'état du projet installé.
- **Option de premier lancement** : proposée à l'utilisateur, **jamais** activée en silence. La configuration locale fait foi.
- **Disponible** ne signifie pas **déjà exécuté** ni **validé sur votre machine**.

### Socle de qualité : présent dans la méthode

| Composant | Par défaut dans la méthode | Précision |
|---|---|---|
| `PREPARE → BUILD → SHIP` | **Obligatoire** | Cadrage et gates adaptés au contexte |
| `PR_SPLIT` / `PR_SCOPE` | **Obligatoire selon la phase** | Une capacité par PR, périmètre et changements vérifiés |
| `Verify` / tests | **Obligatoire** | `gates.require_tests: true` ; `gates.commands: "auto"` détecte les commandes présentes, sans inventer celles qui manquent |
| Reviewer indépendant | **Obligatoire** | Distinct de l'auteur ; une revue absente ou non prouvée bloque la livraison |
| Review Lead Tech, CI et accord de fusion | **Obligatoires selon le risque et SHIP** | Pas d'auto-merge |
| Hook Git `pre-push` | **Installation conditionnelle** | Posé seulement si aucun hook/`core.hooksPath` n'entre en conflit |
| Contrôle de taille des PR | **Avertissement** | Par défaut > 3 fichiers ou > 100 lignes : `mode: "warn"`, pas un blocage |

### Modules opt-in : activables projet par projet

| Module | État du template | Comment l'activer / prérequis | Quand l'utiliser |
|---|---|---|---|
| **Missions successives** | **OFF (absent)** | `run.missions.enabled: true` ; runner compatible et configuration valide ([workflow](docs/agentic/WORKFLOW.md#missions-successives-dune-pr-préparée)) | Enchaîner `test-author → implementer → Verify → reviewer` |
| **Boucle de revue corrective** | **OFF** | `run.review_cycle.enabled: true` + **missions** + `subscription_only` ; onboarding/choix explicite, essai réel ([contrat](docs/agentic/REVIEW_CYCLE.md)) | Faire corriger, revérifier et relire une PR, avec limites persistantes |
| **Double analyse indépendante** | **OFF** | `run.double_analysis.enabled: true` + **missions** + `subscription_only` ; deux CLI/presets admissibles, arbitrage ([contrat](docs/agentic/DOUBLE_ANALYSIS.md)) | Avant BUILD, pour unités **HIGH / EXTRA_HIGH** |
| **TDD explicite (rouge/vert)** | **OFF** | `run.tdd.enabled: true` + choix de workflow ([délégation](docs/agentic/DELEGATION.md#tests-métier-avant-limplémentation)) | Exiger un cycle TDD, distinct des tests métier normalement prévus |
| **Règles avancées de routage** | **OFF** | `routing_policy.enabled: true` + règles et modèles **vérifiés** ([modèles](docs/agentic/MODELS.md), [guide](docs/agentic/MULTI_MODEL_GUIDE.md)) | Choisir explicitement le modèle par rôle/phase, risque ou contrainte |
| **Abonnement uniquement** | **OFF dans le template** | `run.subscription_only: true` et contrôle des CLI/comptes ([guide](docs/agentic/MULTI_MODEL_GUIDE.md)) | Refuser clés API, endpoints et proxies payants ; prérequis des deux modules ci-dessus |
| **Modèle d'exemple DeepSeek / OpenCode** | **OFF** | Entrée `models[].enabled: false` à remplacer/configurer et qualifier ; vérifier le harnais et son mode de facturation | Ajouter un fournisseur si vous le souhaitez ; **ce n'est pas un module d'orchestration** |

**Nuances importantes :**

- Le **routage de base** reste disponible même si `routing_policy` est désactivé ; l'option OFF concerne seulement les règles avancées. Aucun choix de modèle ne prouve à lui seul qu'il a effectivement été lancé.
- Le **reviewer indépendant** est déjà requis ; **`review_cycle`** ajoute les **retours automatiques en correction**, pas un nouvel agent reviewer.
- Le **TDD strict** n'est pas une condition pour disposer de tests. Les configurations documentées rendent le TDD explicite incompatible avec certaines branches de la double analyse ou du cycle correctif ; vérifier les règles avant de les combiner.
- `subscription_only` interdit les chemins API configurés, **mais ne garantit pas** l'absence de dépassement facturé par le fournisseur : désactiver séparément les dépassements payants dans les comptes et vérifier les quotas. Aucun fallback API silencieux.
- **Tickets de consolidation ouverts :** [#127 — missions successives](https://github.com/issa-diallo/agentic-dev-system/issues/127) puis [#128 — boucle corrective](https://github.com/issa-diallo/agentic-dev-system/issues/128). Leur création ne signifie pas que les options sont actives ou validées partout.

## Configuration par projet

En installation LOCAL, le chemin habituel est **`<projet>/.agentic-local/agentic.config.json`**, exclu de Git. Le [template](docs/agentic/templates/agentic.config.json) décrit un **exemple initial**, pas une photographie de toutes les installations. Une installation partagée ou une configuration explicite peut utiliser un autre chemin : **conserver celui renvoyé par l'onboarding**.

**Ordre recommandé :**

1. Vérifier l'état du projet avec l'onboarding, les CLI et les connexions ; conserver les réglages locaux existants.
2. Choisir les modules selon le risque et les dépendances ; activer volontairement, un projet à la fois.
3. Tester les presets et l'exécution réelle avant de déclarer une option opérationnelle ; stopper en `BLOCKED` si les preuves manquent.
4. Utiliser **le même fichier de configuration** pour `inventory`, `quick`, `delegate`, les reprises et le scheduler.

### Exemple de profil optionnel « développement assisté avec corrections »

L'extrait ci-dessous montre **uniquement les clés à intégrer** à la configuration existante ; il n'est pas un fichier autonome et n'active rien tant que le projet n'est pas configuré et testé. Il reflète la politique documentée du [cycle de revue](docs/agentic/REVIEW_CYCLE.md).

~~~json
{
  "run": {
    "subscription_only": true,
    "missions": { "enabled": true },
    "review_cycle": {
      "enabled": true,
      "max_attempts": 7,
      "max_corrections": 2,
      "max_cost_rank": 3,
      "prefer_cross_provider": true,
      "justification": "Confronter les conclusions du développeur"
    },
    "double_analysis": { "enabled": false },
    "tdd": { "enabled": false }
  }
}
~~~

**Attention :** `max_attempts` compte **tous les lancements**, et `max_corrections` uniquement les retours à l'implémentation. La préférence cross-provider reste conditionnée aux modèles/presets autorisés ; elle ne prouve pas à elle seule l'indépendance. La boucle doit s'arrêter au budget fixé, sans effacer les preuves.

### Choisir un profil selon le besoin

| Situation du projet | Approche conseillée | Modules facultatifs |
|---|---|---|
| Petite correction ou documentation | **LIGHT**, revue indépendante et gates adaptés | Aucun nécessaire |
| Application courante, PR préparées | **STANDARD** | Missions successives et, après validation, revue corrective |
| Authentification, paiements, douane, données sensibles | **LARGE** si risque critique | Double analyse HIGH/EXTRA_HIGH si justifiée, revue forte, validation humaine maintenue |
| Plusieurs abonnements et modèles | Tous niveaux | Règles avancées de routage après inventaire/essais |
| Équipe souhaitant du rouge/vert strict | Selon risque | TDD explicite ; vérifier les incompatibilités avant d'activer d'autres modules |

Ces profils sont des **recommandations de configuration**, pas des presets automatiquement installés.

## Commandes et diagnostic

Depuis la racine du projet installé (LOCAL) :

~~~bash
# Afficher la configuration retenue et savoir si le premier lancement est requis
python3 .agentic-local/scripts/agentic-onboard.py status --repo .

# Après configuration : inventaire déclaré et disponibilité des CLI,
# sans supposer l'accès aux modèles ni leur quota
python3 .agentic-local/scripts/agentic-run.py inventory --repo . \
  --config .agentic-local/agentic.config.json

# Observer les sous-agents Codex (panneau de lecture, pas un orchestrateur)
python3 .agentic-local/scripts/agentic-panel.py
~~~

**Remplacer `--config` par le chemin réellement retourné par l'onboarding.** Si le chemin réel diffère, ne pas revenir silencieusement au template. Les commandes `status` et `inventory` ne démontrent pas qu'une mission entière a réussi.

**Reconfigurer :** demander « reconfigurer Agentic » dans le client ayant chargé la méthode ; l'onboarding reprend les seuls choix concernés. [Procédure et précautions](docs/agentic/ONBOARDING.md).

### Mettre à jour une installation existante

~~~bash
git -C ~/agentic-dev-system pull
python3 ~/agentic-dev-system/update-agentic.py ~/mon-projet --dry-run
python3 ~/agentic-dev-system/update-agentic.py ~/mon-projet
python3 ~/mon-projet/.agentic-local/scripts/agentic-pr-check.py install-guard --repo ~/mon-projet
~~~

La mise à jour respecte les configurations et personnalisations locales ; examiner le `--dry-run` et les conflits plutôt que forcer un remplacement. [Guide d'installation](docs/agentic/INSTALL.md).

Si le fichier global Codex existant doit être remplacé **après inspection et sauvegarde** :

~~~bash
cp ~/.codex/AGENTS.md ~/.codex/AGENTS.md.bak
cp ~/agentic-dev-system/codex/global-AGENTS.md ~/.codex/AGENTS.md
~~~

## Documentation de référence

| Sujet | Référence |
|---|---|
| Navigation et règles de la méthode | [Index complet](docs/agentic/README.md), [METHOD](docs/agentic/METHOD.md), [WORKFLOW](docs/agentic/WORKFLOW.md) |
| Installation locale / partagée | [LOCAL](docs/agentic/LOCAL.md), [INSTALL](docs/agentic/INSTALL.md) |
| Premier lancement et configuration | [ONBOARDING](docs/agentic/ONBOARDING.md), [configuration d'exemple](docs/agentic/templates/agentic.config.json) |
| Découpage en PR et livraison | [PULL_REQUESTS](docs/agentic/PULL_REQUESTS.md), [COMMITS](COMMITS.md) |
| Répartition des rôles | [Orchestrator](docs/agentic/roles/ORCHESTRATOR.md), [Implementer](docs/agentic/roles/IMPLEMENTER.md), [Reviewer / Lead Tech](docs/agentic/roles/REVIEWER.md) |
| Modèles, coûts et harnais | [MODELS](docs/agentic/MODELS.md), [MODEL_ROUTING](docs/agentic/MODEL_ROUTING.md), [DELEGATION](docs/agentic/DELEGATION.md), [guide multi-modèles](docs/agentic/MULTI_MODEL_GUIDE.md) |
| Modules avancés | [REVIEW_CYCLE](docs/agentic/REVIEW_CYCLE.md), [DOUBLE_ANALYSIS](docs/agentic/DOUBLE_ANALYSIS.md) |
| Architecture / pratiques de code | [DEVELOPMENT](docs/agentic/DEVELOPMENT.md), [OVERVIEW](docs/agentic/OVERVIEW.md) |
| Sécurité et outils facultatifs | [SAFETY](docs/agentic/SAFETY.md), [OPTIONAL_TOOLS](docs/agentic/OPTIONAL_TOOLS.md) |
| Observation / suivi des agents | [AGENT_PANEL](docs/agentic/AGENT_PANEL.md), [CONTEXT_OBSERVER](docs/agentic/CONTEXT_OBSERVER.md) |

### Contribuer et vérifier le socle

~~~bash
# Dans le dépôt source du framework
python3 -m unittest discover -s tests -v

# Dans un projet installé en LOCAL
(cd .agentic-local && bash scripts/agentic-check.sh --existing)
~~~

Le second contrôle constate la présence des ressources installées ; **il ne remplace pas** les preuves `Verify`, Review, CI ou l'autorisation humaine de fusion.
