# Runtime Scheduler

`scripts/agentic-scheduler.py` distribue les contrats validés par BUILD dans des
worktrees existants. Python stdlib, Git et POSIX `flock` suffisent ; aucun service
permanent ni commande shell issue du manifeste n'est lancé. BUILD, Workspace et
Quality doivent être installés ensemble ; une absence de Quality bloque la
préparation/acceptation au lieu de réduire la fraîcheur des preuves.

## Contrat importable

Importer le script avec `importlib.util`, puis créer
`Scheduler(manifest, repo, state_path=None, skill_roots=(), models=None)`.
Le chemin par défaut est dans le répertoire Git commun :
`agentic-scheduler/<hash-du-chemin-canonique-manifeste>/state.json`.
Ce namespace reste stable quand le contenu du plan change et sépare les missions.
Tous les orchestrateurs d'un même plan doivent
utiliser le même chemin. Workspace protège également les ressources entre états.

`dispatch(adapter)` appelle `adapter.launch(task)` pour chaque tâche indépendante
prête, puis `adapter.wait(task)` pour chacune de celles lancées. Les dépendances
attendent le prochain dispatch après leur achèvement confirmé et leur acceptation
explicite par l'orchestrateur. Une branche bloquée
n'arrête pas les branches indépendantes. Aucun agent RUNNING/ASSIGNED/BLOCKED
n'est relancé automatiquement. La méthode ne crée pas les worktrees et ne merge pas.

Le contrat `task['delegation']` hérite de BUILD : objectif, critères, fichiers,
tests, dépendances, branche/worktree, interdictions et livrable. Tous les fichiers
sont réservés automatiquement via Workspace ; `resources` peut compléter une unité
du manifeste avec des ressources typées `{type, name}`. Les commandes `tests`
restent des instructions à l'agent, jamais des commandes exécutées par le scheduler.

Le contrat `runtime_handshake` demande à l'agent de rester en lecture jusqu'au
reçu confirmé par l'orchestrateur. L'état du worktree est figé à l'attribution,
revérifié juste avant le callback et au reçu ; une édition trop précoce bloque
la tâche et conserve son propriétaire. Le callback launch doit lancer réellement
puis retourner un reçu observé :

```json
{"agent_id":"identifiant-observé", "runtime":"native", "launch_observed":true,
 "identity_verified":true, "model_observed":null}
```

Le callback wait retourne `null` si l'agent est encore actif, ou un handoff :

```json
{"agent_id":"identifiant-observé", "identity_verified":true,
 "stopped_confirmed":true, "outcome":"COMPLETED",
 "result":{"tests":"preuve de validation"}, "blockers":[]}
```

`outcome` accepte COMPLETED/BLOCKED. COMPLETED désigne la fin de l'exécution,
pas une review indépendante, un gate de livraison ou une fusion. Les identités,
résultats et confirmations sont des observations confiées à l'orchestrateur ;
le scheduler ne les authentifie pas. L'orchestrateur vérifie les résultats et
utilise une session distincte pour la review. `accept(pr, evidence)` rend une tâche
COMPLETED utilisable comme dépendance : `status: PASS`, `orchestrator_verified: true`,
`source` non vide, listes `criteria` et `tests` de preuves non vides, `head` Git
actuel, `plan_sha256` actuel et `snapshot` issu de `Quality.snapshot(worktree)`
(accessible également via `scheduler.snapshot`). Le snapshot inclut HEAD, index,
diff binaire et contenu des fichiers untracked. Ces attestations restent sous responsabilité de
l'orchestrateur : le scheduler ne lance pas les tests. Une simple fin d'agent ou
un texte `result` ne débloque jamais les dépendances. Tout nouveau commit/hash
ou changement de contenu, même sans commit et dans le scope autorisé, invalide
l'acceptation et bloque les descendants. Un descendant RUNNING reste actif,
avec son identifiant et ses réservations jusqu'à arrêt confirmé ; BLOCKED ne
signifie jamais arrêté. Les descendants exigent revalidation et un nouvel état,
aucun relancement automatique. Accept n'est pas une autorisation de merge.

Les outils natifs `collaboration` sont appelés par l'orchestrateur hôte ; Python
ne peut pas les appeler. L'adaptateur conserve leur véritable identifiant et
transmet leurs retours. Les tests utilisent `runtime: simulated`, explicitement
sans preuve de sous-agent natif. Le repli `runtime: mono-agent` est explicite :
il ne prétend jamais apporter une review indépendante. Aucun adaptateur
`codex exec` n'est fourni ici. Un processus Codex est une capacité distincte ;
son futur adaptateur devra être opt-in, vérifier la disponibilité et observer
`thread.started` avant d'enregistrer son lancement.

## CLI pour l'orchestrateur hôte

```bash
python3 scripts/agentic-scheduler.py prepare plan.json --repo /repo --pr PR1
# Charger les skills sélectionnés et transmettre les instructions avant lancement.
python3 scripts/agentic-scheduler.py load-skills plan.json --repo /repo --pr PR1
# L'orchestrateur lance ensuite l'agent et vérifie son identifiant runtime.
python3 scripts/agentic-scheduler.py receipt plan.json --repo /repo --pr PR1 \
  --observation /chemin/recu-observe.json
python3 scripts/agentic-scheduler.py handoff plan.json --repo /repo --pr PR1 \
  --observation /chemin/fin-confirmee.json
# Après vérification réelle des critères, tests et contrat par l'orchestrateur.
python3 scripts/agentic-scheduler.py accept plan.json --repo /repo --pr PR1 \
  --observation /chemin/validation-verifiee.json
python3 scripts/agentic-scheduler.py resume plan.json --repo /repo
```

`--state /chemin/state.json` choisit un état local explicite. `prepare` produit
ASSIGNED et une réservation, aucun lancement. `receipt` exige l'attestation
`identity_verified`; un nom JSON seul ne constitue pas une preuve d'identité.
La CLI renvoie toujours `identity_authenticated: false`, y compris après un reçu
accepté. Ne pas exposer ces commandes aux agents non fiables : cette interface
coopérative est réservée à l'orchestrateur autorisé.

## Reprise, ownership et observations

États persistants : PLANNED → ASSIGNED → RUNNING → COMPLETED, ou BLOCKED.
Les mutations sont sous `flock`, les JSON écrits par remplacement atomique et
`fsync`. L'intention de réservation est sauvegardée avant Workspace, permettant
de détecter une interruption entre les deux registres. L'attribution est
sauvegardée avant le callback launch. Une interruption pendant launch conserve
ASSIGNED et le propriétaire ; l'orchestrateur doit retrouver l'agent ou confirmer
son arrêt, jamais relancer aveuglément.

Un timeout, une exception launch/wait ou une modification de plan ne libère pas
une réservation. `handoff` libère seulement après confirmation d'arrêt. Un arrêt
confirmé sans lancement observé peut clôturer une attribution en BLOCKED avec
`agent_id: null`; il ne peut pas produire COMPLETED. Une disparition externe de
réservation bloque la tâche et exige une réconciliation par l'orchestrateur.
Une exception launch sans reçu laisse `launch_status: UNKNOWN`, `active: null` :
le scheduler ne connaît pas la réalité du lancement. Un reçu runtime valide mais
un Git/contrat devenu invalide conserve l'identité observée, `active: true` et
BLOCKED ; il ne transforme jamais l'erreur de scope en arrêt fictif.

Le SHA initial est enregistré à l'attribution. `handoff` et `accept` contrôlent
le diff commité depuis ce SHA et les fichiers dirty ; un commit propre hors scope
bloque également la tâche. Les réservations demeurent jusqu'à l'arrêt confirmé.

`resume` relit et valide le plan, son hash, les branches/worktrees Git, les fichiers
modifiés et les propriétaires. Une unité modifiée ou supprimée et ses descendants
sont bloqués avant dispatch ; les unités indépendantes inchangées continuent.
Une modification des métadonnées globales invalide toutes les unités existantes.
Après revalidation et arrêt des anciens agents, utiliser un nouvel état pour le
plan révisé ; aucune réinitialisation automatique ne masque l'ancien historique.

La trace conserve identifiant runtime, rôle, état, résultat, blockers, hash du
plan, événements horodatés et durée de lancement à arrêt mesurée. Le modèle
demandé est distinct du modèle observé (ou `null`), jamais déduit du demandé.
Tokens, coûts et quotas ne sont pas calculés. Les callbacks évitent les secrets
dans leurs retours, car résultats/blockers restent dans le JSON local.

Si les scripts Skills/Models sont présents, `skill_roots` active la sélection
et `models` fournit l'inventaire à router. Un routage impossible bloque la tâche.
La classification utilise les métadonnées facultatives `routing: {type, risk,
complexity}` de l'unité, validées par Models. Objectif/fichiers impliquant auth,
permissions, secrets, sécurité/authentification françaises ou migrations SQL
imposent conservativement un niveau fort, même sans métadonnées. Les mots sont
normalisés et reconnus aux frontières ; « author » n'est pas interprété comme « auth ».
Les familles authenticated/authentifiée et authorized/autorisé, ainsi que login,
sign-in, OAuth et JWT, sont reconnues dans les objectifs et chemins. Cette
inférence conservatrice prime sur une métadonnée qui sous-estimerait leur risque.
La recommandation est transmise comme `model_requested`, sans changement du
modèle principal. `model_applied` devient vrai uniquement si l'observation complète
du modèle correspond à la demande. Sans composants/configuration, ces champs
restent vides/null.

Les skills conservent trois observations distinctes : `selected`, `loaded`,
`applied`. Dispatch lit les skills sélectionnés avant launch et transmet leur
contenu dans `skill_instructions` au callback, sans persister les instructions.
Pour le parcours CLI, `load-skills` est obligatoire avant receipt si des skills
ont été sélectionnés. `load_skills(pr)` lit explicitement les instructions sélectionnées et
retourne leur contenu au caller, en conservant leurs hashes dans l'état. Un
handoff peut fournir `skills_applied: [{path, sha256, evidence}]`, accepté uniquement
pour un skill chargé et une preuve non vide. Lire n'implique jamais appliquer.
