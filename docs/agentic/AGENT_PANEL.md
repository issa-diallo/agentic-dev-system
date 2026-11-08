# Panneau compagnon des agents

Le panneau affiche les sous-agents Codex observés et leur état dans un second
terminal. Il est facultatif : le fermer ne ferme ni les agents ni Codex.
Il ne crée pas de session modèle et ne valide aucun gate.

## Lancer le panneau

Garder Codex dans le premier terminal. Ouvrir un deuxième terminal à la racine du
même projet, puis lancer :

```bash
python3 .agentic-local/scripts/agentic-panel.py
# Dépôt source ou installation partagée :
python3 scripts/agentic-panel.py
```

Le terminal doit pouvoir joindre le serveur local utilisé par Codex. Le panneau
se connecte au serveur déjà lancé ; il ne le démarre pas et ne change ni son compte,
ni sa configuration, ni ses permissions. Il ne divise pas automatiquement la fenêtre :
un deuxième onglet, une fenêtre voisine ou un volet de votre terminal convient.

Avec une sortie terminal interactive, le panneau se rafraîchit et restaure
l’affichage précédent à la sortie avec **Ctrl-C**. Avec une sortie redirigée ou
un pipe, il produit un seul état instantané.

## Lire l’affichage

| Rôle observé | Couleur |
|---|---|
| `explorer`, `agentic_explorer`, `agentic-explorer` | Bleu |
| `implementer`, `agentic_implementer`, `agentic-implementer` | Vert |
| `reviewer`, `agentic_reviewer`, `agentic-reviewer` | Violet |
| Autre rôle ou rôle indisponible | Neutre |

Les couleurs servent à distinguer les rôles ; le texte indique l’état. Le surnom
ou l’identifiant permet de repérer l’agent. Les noms de mission ne servent pas à
deviner un rôle absent des métadonnées du runtime.

| État Codex | Sens affiché |
|---|---|
| `active` | Actif ; attente d’autorisation ou d’entrée si le runtime le précise |
| `idle` | Au repos |
| `notLoaded` | Non chargé |
| `systemError` | Erreur |
| État absent ou inconnu | Inconnu |

**Au repos ou non chargé ne signifie pas travail terminé ni Verify/Review PASS.**
Le panneau ne déduit aucun état Agentic à partir de l’état d’exécution.

Une liste vide signifie qu’aucun sous-agent n’a été retourné pour ce périmètre.
Une erreur de connexion affiche une indisponibilité, et non une fausse liste vide.
Pendant une panne, les anciennes lignes ne sont pas présentées comme actuelles.
Les limites de résultats ou de place à l’écran sont signalées.

## Options utiles

```bash
# Un seul affichage sans mode interactif
python3 scripts/agentic-panel.py --once

# Snapshot JSON minimal, sans codes de couleur
python3 scripts/agentic-panel.py --json

# Pas de couleur ; NO_COLOR est aussi respecté en mode auto
python3 scripts/agentic-panel.py --color never

# Autre dépôt et rafraîchissement toutes les deux secondes
python3 scripts/agentic-panel.py --repo /chemin/du/projet --interval 2

# Socket explicite d’un serveur Codex existant
python3 scripts/agentic-panel.py --socket /chemin/app-server-control.sock
```

En installation locale, remplacer `scripts/` par `.agentic-local/scripts/`.
`--timeout` borne l’observation (maximum 60 secondes) ; `--limit` limite les résultats
(de 1 à 200). `--interval` accepte de 0,2 à 3600 secondes.
`--color auto` est la valeur par défaut ; `always` force la couleur et `never`
la désactive. Le JSON reste sans séquences de couleur. `--help` ne nécessite
pas de serveur. Une observation unique échouée renvoie un code de sortie non nul.

## Périmètre et source

La V1 utilise le client local **Codex**, avec `codex app-server proxy` et le
transport WebSocket du socket Unix. Elle lit les métadonnées des sous-agents via
l’interface [App Server officielle](https://learn.chatgpt.com/docs/app-server).
Une version de Codex ne proposant pas ce proxy ne permet pas cette connexion.
La connexion et la lecture ont été vérifiées avec Codex CLI 0.167.0.
Un rôle ou état non exposé reste inconnu.

Le filtrage couvre le répertoire demandé et les racines de ses worktrees Git connus,
puis vérifie à nouveau le périmètre côté client. La liste est un lot récent borné,
pas un historique exhaustif ; une suite de résultats est signalée comme tronquée.
Les threads non chargés peuvent donc apparaître, avec leur état explicite.
Les sessions utilisant un autre serveur, un autre `CODEX_HOME` ou un client embarqué
avec `--no-daemon` ne sont pas implicitement jointes. Aucun backend Claude n’est
inclus dans cette V1.

L’observateur n’émet que l’initialisation du protocole et une lecture de liste de
threads. Il demande la lecture de la base d’état sans réparation des métadonnées.
Il n’envoie ni prompt, ni demande de lancement, reprise, interruption ou approbation.
La sortie est réduite aux identifiants, rôle, surnom, état, répertoire et parent :
les aperçus de conversation et messages ne sont jamais affichés ni exportés.
Les caractères de contrôle provenant des métadonnées sont neutralisés.

L’observateur peut aussi être utilisé seul pour un snapshot JSON :

```bash
python3 scripts/agentic-observe.py --repo .
```

Les trois scripts (panneau, observateur et transport) et ce guide sont distribués
par l’installateur et la mise à jour habituels. Aucun lancement automatique ni
service permanent n’est ajouté.
