# Observateur de reconnexion de contexte

Source unique, versionnée et réutilisable pour décider si une reconnexion TUI Codex a gardé
**un seul tour produit**. Chaque recette l'invoque ; elle ne recopie pas le classificateur.
Le lanceur `scripts/agentic-context-launch.py` et son contrat ne changent pas.

## Composants

| Fichier | Rôle |
|---|---|
| `scripts/agentic-context-capture.py` | Capture passive : relais Unix privé TUI → serveur dédié, octets inchangés, métadonnées seulement. |
| `scripts/agentic-context-observe.py` | Observateur : `snapshot` avant reconnexion, `verify` après. API `snapshot(request, backend=None)` et `verify(request, before, backend=None)`. |

Capture et observation sont séparées : la capture ne décide rien, l'observateur ne relaie rien.

## Usage canonique

1. Lancer la capture sur un dossier privé (0700) : `agentic-context-capture.py --upstream
   <socket serveur dédié> --tui <socket privé> --report <capture.json>`. Le rapport est réécrit
   toutes les 0,25 s et à l'arrêt ; attendre un cycle après la dernière activité avant
   d'observer. En Python : `with CaptureProxy(upstream, tui) as proxy: ... proxy.report()`.
2. La recette ne réécrit que l'endpoint `--remote` des terminaux vers `--tui`. Serveur,
   RPC, modèle, permissions et tours du lanceur restent originaux.
3. Requête JSON : `state` (état du lanceur), `receipt` (reçu du lanceur), `capture`
   (rapport de capture), `codex_home` (optionnel ; défaut `CODEX_HOME` ou `~/.codex`).
4. Après la fin de la réponse produit, avant de fermer le TUI :
   `agentic-context-observe.py snapshot --request req.json > before.json`
5. Fermer le seul TUI possédé, relancer le lanceur avec `--reconnect`, puis :
   `agentic-context-observe.py verify --request req.json --before before.json`

Sortie JSON ; code 0 `PASS`, 1 `BLOCKED`. Aucun prompt, titre, transcript ou texte d'erreur
n'est écrit : seulement des identifiants, des codes de refus et des SHA-256.

## Rapport

- `raw_verdict` : règle historique stricte (le seul thread chargé est le produit), avec
  `raw_reasons`.
- `verdict` : verdict réconcilié, avec `reasons` (codes fixes). Seul un thread auxiliaire
  prouvé peut différer du brut.
- `auxiliary_threads` : threads prouvés, avec connexion, tour, hash du titre et `loaded`.
- `counts` : `task_started` / `task_complete` sur tout le rollout produit, toujours
  collectés, même en cas de refus. `processes` : pid, starttime, rôle, exécutable.

## Preuve stricte d'un thread de nommage

Un thread supplémentaire est toléré uniquement si la capture montre, sur **une même
connexion TUI** (`initialize` avec `codex-tui` réussi) :

1. `thread/start` d'id `temporary-structured-*`, `ephemeral`, réponse positive donnant l'ID
   auxiliaire éphémère ;
2. exactement un `turn/start` sur cet ID, réponse positive avec l'ID du tour ;
3. un seul message final `agentMessage` / `final_answer` de ce tour (texte ou objet JSON à
   un champ chaîne ; autre forme : ambigu), puis `turn/completed` avec le même tour ;
4. ensuite un seul `thread/name/set` visant le **thread produit**, dont le hash du nom égale
   celui de la sortie, avec réponse positive de même identifiant ;
5. aucune requête ni aucun item d'outil, aucun autre tour, aucun rollout auxiliaire dans
   `sessions` ou `archived_sessions` ;
6. cycle de vie Codex 0.169, chaque événement sous corrélation exacte (même connexion,
   sens, thread auxiliaire) : `turn/moderationMetadata` serveur du tour auxiliaire, entre
   `turn/start` et `turn/completed` ; `thread/unsubscribe` optionnel, unique, requête client
   après `turn/completed`, réponse positive de même identifiant ; `thread/closed` optionnel,
   unique, notification serveur après cette réponse, puis plus aucun événement auxiliaire.
   Un auxiliaire déjà déchargé au `snapshot` donne `raw_verdict` PASS (normal) ;
7. l'auxiliaire est déjà connu au `snapshot` (un nouveau après lui est refusé).

8. **Lectures après nommage (seule exception).** Une fois la chaîne 1–6 complète, y compris
   la réponse positive de `thread/name/set`, sont tolérées des paires de requêtes client
   `thread/read` ou `thread/turns/list` visant l'auxiliaire, chacune suivie de **sa** réponse
   serveur positive unique (même identifiant, même connexion, sens serveur, `seq` ultérieur).
   La connexion de lecture est celle du nommage, d'un TUI d'avant la reconnexion ou du TUI
   reconnecté : elle doit s'ouvrir par un `initialize` client `codex-tui` dont la réponse
   positive précède la lecture. Les lectures valent après `thread/unsubscribe` et
   `thread/closed` sans les rouvrir. Cycle normal : la fermeture originale peut suivre une
   lecture (après `thread/unsubscribe`) ; APRÈS `thread/closed`, aucun autre événement
   auxiliaire n'est admis hors des paires de lecture prouvées. Preuve de forme et de tour :
   la réponse doit porter le corps exigé par le schéma (`thread/read` : `result.thread`
   objet avec `id` et `turns` tableau ; `thread/turns/list` : `result.data` tableau) et chaque
   Turn lu un `id`, un `status` et un tableau `items` (vide admis). Tout Turn lu doit être le
   seul tour auxiliaire de nommage, d'id identique et `completed` ; autre id, autre statut,
   second tour, corps manquant ou mal formé, ou métadonnée de tour/item contradictoire sur la
   requête ou la réponse donnent `BLOCKED`. Refus (`BLOCKED`) : requête sans réponse, réponse en
   erreur, dupliquée, antérieure, d'id ou de connexion différents, connexion sans `initialize`
   `codex-tui` réussi, lecture avant la réponse de nommage, nommage ou lecture depuis une
   connexion non qualifiée. Les items de la réponse restent soumis aux règles 5 : pas
   d'outil ni d'item inconnu, identité et sortie du final cohérentes avec celles du nommage
   dans toutes leurs représentations. `thread/resume`, `turn/start`, souscription et toute
   autre méthode, les rollouts auxiliaires et `AUXILIARY_NOTIFICATIONS` restent inchangés.

La capture n'extrait les métadonnées de tours de `result.data` que pour une réponse positive
corrélée (même connexion et id, sens serveur) à une requête client `thread/turns/list` ; les
réponses `thread/list` ou non corrélées ne sont pas lues comme listes de tours. Aucun texte,
paramètre, commande, titre ou erreur n'est conservé.

Le préfixe, le timing ou un booléen fourni par l'appelant ne prouvent jamais le nommage.
Tout autre `thread/start`, thread chargé inconnu, flux invalide, tronqué, trop gros, lacunaire
ou capturé tardivement, erreur de collecte, ou ambiguïté donne `BLOCKED`.

Après reconnexion : exactement un `task_started` et un `task_complete`, du tour du reçu, sur
l'ensemble du rollout produit (JSONL invalide ou second tour : `BLOCKED`).

Processus : seul un exécutable `codex` (`/proc/<pid>/exe`) peut être `server` (`app-server
--listen unix://<amont>`) ou `tui` (`--remote unix://<tui>`). Les wrappers (Python, GNOME
Terminal) citant ces arguments sont `wrapper`. Le serveur doit garder pid et starttime du
lanceur.

## Raccord au backend existant

`LocalBackend` n'ajoute que deux frontières : `rpc` réutilise `RealBackend.rpc` du lanceur
(transport existant, requêtes `thread/loaded/list` et `thread/read` seulement) et
`processes` lit `/proc` pour l'UID courant. Les tests les remplacent par un backend
`rpc(endpoint, method, params)` / `processes(endpoints)`. Aucun changement du lanceur.

## Analyse de `_identify` (AC6)

Chronologie du lanceur : `_start` lance le serveur, vérifie qu'il ne charge aucun thread, lance
le TUI, appelle `_identify` (attend exactement un thread chargé, refuse plusieurs), puis
`_submit` envoie `turn/start`. Observation historique : le thread de nommage apparaît après la
première soumission (et non à la fin du tour produit), donc après `_identify`, qui ne le voit pas. Ce n'est qu'une chronologie observée,
pas une causalité prouvée : rien ne démontre que le nommage exige une sortie d'agent, et
l'observateur ne s'en sert pas — seule la chaîne capturée (ci-dessus) qualifie l'auxiliaire.
`_reconnect` ne rappelle pas `_identify` : le thread auxiliaire encore chargé ne bloque donc pas
la reconnexion, et c'est l'observateur qui le qualifie.

Limites : le risque qu'un thread auxiliaire apparaisse avant la fin d'`_identify` n'est pas
observé ; le lanceur le refuserait (« Plusieurs threads »), garde intacte, sans assouplissement
ici (aucun changement du contrat du lanceur). Ordre notification/réponse à `turn/start` non
garanti par le protocole : non présumé ; les notifications de tour doivent seulement suivre la
requête. Un rapport de capture pris en connexion vivante avec un en-tête, une trame ou un
fragment incomplet porte l'erreur transitoire `incomplete-stream` (`BLOCKED`) ; elle disparaît
si les octets suivants complètent le message, alors qu'une fermeture tronquée reste
définitive. Les items embarqués des tours (`turn.items`) sont conservés en métadonnées
(type, id, phase, hash) ; tout type hors message/raisonnement ou forme inconnue refuse la preuve.
L'identité du message final (id, hash, non ambigu) est confrontée à toutes les représentations
du même auxiliaire (réponses, notifications, récapitulatifs de tour) : une répétition cohérente
du même item est acceptée ; id différent, sortie différente ou ambiguë, ou second final : `BLOCKED`.
La capture doit commencer à `seq` 1 et être continue : tout événement retiré (outil compris) ou
début manquant donne `BLOCKED`, même si la chaîne restante est valide (la coalescence des deltas
ne consomme pas de numéro).
Structure des événements de capture et JSON non conforme (y compris `NaN`) : `BLOCKED` en API
comme en CLI, compteurs de rollout conservés, sans message d'erreur exporté. Format du
protocole (id `temporary-structured`, `final_answer`, `thread/name/set`) observé en 0.169 ;
aucune garantie inter-version : tout écart donne `BLOCKED` et demande une capture de diagnostic.
