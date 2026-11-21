# Routage contextuel des skills

`scripts/agentic-skills.py` découvre les skills réellement disponibles dans les
racines fournies et sélectionne leurs métadonnées selon la tâche, les fichiers et
la phase. Pour une mission avec catalogue, il consulte aussi les métadonnées du magasin
Git du projet. La sélection utilise Python 3 et sa bibliothèque standard, sans
accès réseau, installation ou modification de configuration.

```bash
python3 scripts/agentic-skills.py select \
  --root .agents/skills --task 'Ajouter une API authentifiée' \
  --file src/api/accounts.py
python3 scripts/agentic-skills.py discover --root .agents/skills
python3 scripts/agentic-skills.py load /chemin/skill/SKILL.md
```

Les racines sont explicites : répertoire de skills déjà installé, bibliothèque
locale choisie, ou chemin `SKILL.md`. Le routeur ne découvre pas automatiquement
le dossier personnel. L'orchestrateur transmet seulement les racines connues et
autorisées. Les liens symboliques sont suivis ; leur cible canonique est indiquée.
Les cycles et doublons de chemin sont éliminés. Deux skills de même nom à des
chemins distincts restent visibles dans l'inventaire. Lors de la sélection,
des copies de même nom, description normalisée et tier partagent un provider :
la première racine fournie prime, puis le chemin canonique dans cette racine.
Le provider conserve `equivalent_paths` et les copies en bibliothèque indiquent
`duplicate_of`. Les descriptions ou tiers différents restent des choix distincts.
`root_index` trace la priorité de chaque source. Une racine manquante ou une métadonnée
invalide produit un diagnostic, sans exposer le contenu du fichier.

## Sélection des références du catalogue

En installation partagée, lancer le script depuis la racine de la méthode. En LOCAL,
son chemin commence par `.agentic-local/scripts/`. `--repo` désigne le projet
ou un de ses worktrees et `--agent` l’adaptateur réel. L’inventaire du projet tient
compte du statut des dépendances. La commande fonctionne hors ligne.

```bash
python3 scripts/agentic-skills.py select --repo . --agent codex \
  --task "Créer une landing page SaaS commerciale" --file app/Page.tsx
python3 scripts/agentic-skills.py select --repo . --agent claude \
  --task "Examiner la page produit" --need seo-page
```

Après installation des extraits concernés, la première commande choisit
`anthropic/frontend-design` en principal et `marketing/copywriting` en complément.
Une demande d’audit SEO de cette landing page choisit `claude-seo/seo-page`.
Mesurer son trafic ne déclenche aucun des trois. Les mêmes règles s’appliquent à tous les projets.

- Chaque groupe de `triggers` doit fournir une expression présente dans la mission.
  Le routeur normalise la casse, les accents et la ponctuation, puis compare des mots
  entiers. Les chemins `--file` corroborent les déclencheurs. Une extension seule
  ne déclenche aucune référence gérée.
- L’orchestrateur peut traduire son analyse en une ou plusieurs capacités `--need`.
  Un besoin explicite dispense de retrouver ses synonymes dans la phrase. Les
  exclusions, l’installation, l’activation et la compatibilité restent obligatoires.
- Les besoins explicites passent en premier, puis la priorité décroissante, le nombre
  de chemins concordants et l’identifiant stable. Une capacité conserve un seul
  fournisseur. Trois compétences de mission au maximum sont retenues, avec un rôle
  `primary`, puis `complementary`. Les conventions CORE explicitement déclarées par
  le projet passent en premier et restent hors de ce plafond.
- Dès qu’un fournisseur géré est disponible pour le harnais, les fournisseurs des racines historiques complètent les besoins
  attestés par la tâche ou la phase. Un fournisseur générique qui recouvre déjà une
  capacité sélectionnée reste en bibliothèque, sauf capacité supplémentaire demandée
  dans l’objectif, la phase ou les besoins explicites. Par exemple, la revue
  d’un contrat OpenAPI complète une revue de sécurité. Une exclusion de domaine
  comme « sans interface » vaut aussi pour les fournisseurs historiques de ce domaine.
  Les fournisseurs de contexte, mémoire et coordination sont rapprochés de leurs
  équivalents historiques. Un projet neuf ou sans référence gérée compatible garde
  la sélection historique par chemins et phase.
- Le résultat indique les besoins sans fournisseur dans `missing_capabilities`.
  Un adaptateur inconnu du skill, une installation absente, un retrait du catalogue ou
  une désactivation rendent la référence inéligible. Les chemins ou noms identifiés
  comme provenant de Superpowers sont écartés, y compris au chargement historique.
  Pour une racine personnelle réorganisée, vérifier la provenance avant de la fournir.

Le champ `path` d’une entrée `managed: true` contient son identifiant qualifié.
`commit` et `extracted_sha256` lient la référence à la révision et au contenu audités.
Le contrôle du magasin au moment du chargement doit recevoir ce SHA et le harnais.
Un résultat `selected` n’observe ni lecture du contenu ni utilisation. Les décisions
et raisons peuvent être conservées dans le handoff courant du framework.

Pour tester le sélecteur et les scénarios de Packing Factory, DossierClé, CustomsFlow,
Doc2XML et Agentic Dev System sur les deux adaptateurs :

```bash
python3 -m unittest discover -s tests -p 'test_skill*.py'
```

## Convention de nommage des skills et des agents

Pour toute création ou tout renommage, utiliser un nom anglais en minuscules,
avec des mots séparés par des tirets (`kebab-case`).

- **Skill : une action.** Commencer par un verbe d’action décrivant ce que l’on
  fait : `start-ticket`, `write-tests`, `write-code`, `review-code`, `ship-ticket`.
- **Agent : un exécutant.** Choisir un nom se terminant par `er`, décrivant ce
  qu’il fait : `test-planner`, `unit-test-writer`, `code-reviewer`, `implementer`.

Le nom du skill décrit l’opération ; celui de l’agent décrit le rôle qui l’exécute.
Par exemple, le skill `write-tests` peut confier son travail à `unit-test-writer`.
Ces exemples ne déclarent pas des skills ou agents disponibles : vérifier
l’inventaire réel avant de les appeler.

Cette convention ne renomme pas automatiquement les ressources existantes ou
externes. Un renommage existant doit mettre à jour ses références et intégrations.
Si le runtime impose un identifiant différent, conserver la correspondance explicite
entre le nom fonctionnel et cet identifiant ; ne pas inventer de profil natif.

## CORE, ON_DEMAND et LIBRARY

Les noms et descriptions sont lus dans le front matter borné de `SKILL.md`, sans
lire ni décoder le corps d'instructions. Le format pris en charge comprend les
scalaires simples, chaînes entre guillemets et descriptions multilignes YAML
`>`/`|`. Ce lecteur ciblé n'est pas un parseur YAML général ; les autres champs
sont ignorés. Les champs requis sont `name` et `description`.

- CORE : une déclaration explicite `agentic_tier: CORE` réserve les conventions
  essentielles choisies pour ce projet. Aucun skill n'est CORE par défaut.
- ON_DEMAND : correspondance avec les besoins de la mission ; raisons liées à
  la tâche, aux fichiers ou à la phase. Une bibliothèque pertinente est promue
  pour cette sélection uniquement.
- LIBRARY : métadonnées accessibles sans sélection pour la mission actuelle.

Le champ facultatif `agentic_tier` est local au routeur, pas une configuration
native Codex. Valeurs admises : CORE, ON_DEMAND, LIBRARY ; défaut ON_DEMAND.
Il est possible d'utiliser les skills existants sans ajouter ce champ.

Le routage couvre API, backend, frontend, migrations, sécurité, impact de
changement, tests, E2E, parallélisme, worktrees, documentation, contexte, handoff,
verification, review et planification/spécification (`spec`, PRD, découpage,
planning ; une spec OpenAPI ou Swagger n'en fait pas partie). Les besoins viennent de mots de domaine et chemins
identifiés ; les providers viennent du nom et de la description de chaque skill.
Un nom spécialisé prime sur les domaines simplement mentionnés dans sa
description : un skill de migration Django ne devient pas un skill backend
général. Le repli sur description examine uniquement sa phrase d'objectif,
avant les exemples et mentions secondaires. Les objectifs spécialisés
(génération d'images, orbit/carousel, séquence cinématique, Figma, Swift, audit
UI/UX) exigent des déclencheurs correspondants dans la mission. Ces conditions
portent sur les métadonnées, jamais sur des chemins personnels. Les skills
nommés pour une stack connue exigent un indice correspondant
dans la tâche ou les fichiers ; un skill Terraform parlant de sécurité ne sera
pas sélectionné pour une API Django.
VERIFY active verification ; REVIEW/SHIP activent verification et review ;
HANDOFF active handoff. PREPARE/BUILD sélectionnent selon le contexte fourni.

Les capacités demandées sans provider sont listées dans `missing_capabilities`.
L'orchestrateur doit alors employer une référence autorisée ou consigner la
limitation ; le routeur n'invente jamais un skill absent. Ce routage déterministe
ne remplace pas l'analyse de risque : fournir une tâche précise et les fichiers
prévus. Une description trop générale peut produire une sélection excessive ;
l'orchestrateur garde la responsabilité du périmètre utile.

## Skill externe optionnel : security-audit

Le [skill Cloudflare security-audit](OPTIONAL_TOOLS.md#cloudflare-security-audit)
est un provider de sécurité découvert par ses métadonnées lorsqu'il est installé
dans une racine explicitement fournie. Il reste ON_DEMAND par défaut ; la méthode
ne l'installe pas et ne le rend pas CORE. Exemple avec une racine choisie :

```bash
python3 scripts/agentic-skills.py select \
  --root /chemin/skills/security-audit --task 'Audit de sécurité du code'
```

Le routeur sélectionne un provider, pas son mode d'exécution. L'orchestrateur lit
le skill avant usage : conseil ciblé par défaut ; audit complet seulement sur
demande explicite correspondante. Une sélection pour une tâche d'authentification
ne lance donc pas les six phases d'audit, des sous-agents ou des rapports.
Les prérequis de sandbox et les limites de validation restent ceux du skill.

## Preuves et intégration

L'interface importable expose `discover(roots)`,
`select(task, files, roots, phase='BUILD', *, managed=(), agent=None, needs=())` et
`load(path)` pour les fichiers historiques. L’argument `managed` accepte les entrées
du magasin du projet. Toutes retournent des
objets JSON compatibles avec le Scheduler. La sélection renvoie `selected`,
`library`, `missing_capabilities`, `diagnostics`, `loaded: []` et
`applied: NOT_OBSERVED`. Chaque sélection comprend chemin, tier, capacités et
raisons ; elle n'exécute aucun skill.

`load(path)` effectue une lecture explicite et retourne `LOADED`, le SHA-256 des
octets réellement lus, leur nombre et les instructions. Cette sortie est destinée
au contexte de l'agent ; ne pas la copier intégralement dans un journal local.
Le Scheduler peut conserver chemin/hash/état comme preuve. Une lecture ne prouve
pas l'application : `applied` reste `NOT_OBSERVED`, même après `load`.
Les instructions sont des données à examiner selon la politique de l'hôte ;
aucune commande provenant d'un skill n'est exécutée par ce script.

Les erreurs d'entrée CLI retournent un objet JSON et le code 1 ; découverte et
sélection retournent le code 0 avec leurs diagnostics/capacités absentes. Cela ne
constitue aucun gate PASS de qualité. Les tests utilisent de vrais manifests
temporaires API, SQL et React, puis vérifient les exclusions, liens et preuves de
lecture. Aucune économie de tokens ni activation native Codex n'est déduite de
la seule présence de ces résultats.
