# Routage exécutable des modèles

`scripts/agentic-models.py` expose `route(task, capabilities, attempts=[])` et une
CLI prenant un fichier JSON avec ces trois champs. Le résultat est une
recommandation pour un sous-agent, jamais un changement du modèle principal.
`applied: false` reste obligatoire : le Scheduler doit lancer réellement l'agent
avec les options supportées et conserver la preuve du modèle effectivement utilisé.

L'inventaire fourni par l'orchestrateur contient `models` et `runtime_overrides`
(booléen). Chaque modèle fournit `id`, `max_level` (ou `strength`) parmi LOW,
MEDIUM, HIGH, EXTRA_HIGH ; alternativement `tiers` liste précisément ses niveaux.
Il fournit aussi `efforts` réellement disponibles et `cost_rank`, un classement
relatif vérifié par l'appelant, sans prix implicite. Le routeur ne découvre pas
les droits d'un compte. Sans override, la recommandation reste consultative.
Une capacité insuffisante bloque ; aucune équivalence tarifaire n'est inventée.

`task` fournit `id`, `type`, `complexity`, `risk`. Une lecture/documentation simple
à risque faible relève de LOW ; une implémentation cadrée de MEDIUM ; architecture,
refactoring, review ou complexité élevée de HIGH. Risque critique, authentification,
autorisation, sécurité et migrations imposent EXTRA_HIGH. Les types doivent être
normalisés par l'orchestrateur ; ce routeur n'analyse pas le langage naturel.
Les efforts connus sont low, medium, high et xhigh ;
une valeur inconnue n'est jamais transmise. Max et Ultra ne sont pas
interprétés comme des équivalences portables de reasoning_effort. Le plus faible effort suffisant et le
plus faible cost_rank capable sont retenus, sans imposer un fournisseur.

Chaque tentative concerne un `task_id`. Une escalade requiert `outcome: FAIL`,
`level` observé, `diagnosis_kind: capacity` et une `diagnosis` concrète. Une erreur
sans diagnostic ou une erreur d'implémentation bloque la relance automatique :
analyser/corriger la cause, puis soumettre une nouvelle tâche ou tentative corrigée.
Toutes les observations fournies doivent porter un task_id non vide, un outcome
PASS ou FAIL et un level valide ; un état inconnu bloque même si une observation PASS suit. L'ordre
fourni est chronologique et fait autorité ; les timestamps optionnels ne servent
pas à trier silencieusement l'historique. Un PASS de correction, vérifié par
l'orchestrateur, clôt les échecs précédents sans les retirer de attempt_history
ni du compteur. Un nouvel échec non diagnostiqué bloque de nouveau. Un échec au
niveau maximal nécessite un handoff. Les échecs d'autres tâches
n'augmentent jamais le niveau d'une nouvelle tâche simple.

Les métriques tokens, api_cost, codex_quota et duration_seconds restent null tant
que le runtime ne les expose pas. Le nombre de tentatives fourni est observable ;
un classement relatif ne démontre ni coût API ni économie de quota Codex.
