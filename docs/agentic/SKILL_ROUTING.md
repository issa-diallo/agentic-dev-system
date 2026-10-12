# Routage contextuel des skills

`scripts/agentic-skills.py` découvre les skills réellement disponibles dans les
racines fournies et sélectionne leurs métadonnées selon la tâche, les fichiers et
la phase. Python 3, bibliothèque standard uniquement ; aucune installation de
skills, aucun accès réseau ni modification de configuration personnelle.

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
Les cycles et doublons de chemin sont éliminés, mais deux skills de même nom à
des chemins distincts restent visibles. Une racine manquante ou une métadonnée
invalide produit un diagnostic, sans exposer le contenu du fichier.

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
verification et review. Les besoins viennent de mots de domaine et chemins
identifiés ; les providers viennent du nom et de la description de chaque skill.
Un nom spécialisé prime sur les domaines simplement mentionnés dans sa
description : un skill de migration Django ne devient pas un skill backend
général. Les skills nommés pour une stack connue exigent un indice correspondant
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

## Preuves et intégration

L'interface importable expose `discover(roots)`,
`select(task, files, roots, phase='BUILD')` et `load(path)`. Toutes retournent des
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
