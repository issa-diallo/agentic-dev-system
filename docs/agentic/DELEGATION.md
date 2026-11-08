# Délégation à des modèles économiques

Un agent fort cadre et vérifie ; un modèle moins cher implémente un périmètre fermé.
Quatre scripts stdlib l'outillent, sans service permanent ni dépendance :

| Script | Rôle |
|---|---|
| `agentic-run.py` | route le modèle, lance le harnais CLI, applique les gates, enregistre les tentatives |
| `agentic-brief.py` | rend le brief fermé et lit le handoff structuré |
| `agentic-gates.py` | gates déterministes sur le diff, sortie prête pour `scheduler accept` |
| `agentic-claude.sh` | lance Claude Code avec les rôles de `claude/agents/` (équivalent de `agentic-codex.sh`) |

## Démarrage rapide

```bash
cp docs/agentic/templates/agentic.config.json agentic.config.json   # racine de la méthode
python3 scripts/agentic-run.py inventory                            # modèles réellement disponibles
python3 scripts/agentic-run.py quick --id csv-export \
  --objective "Ajouter l'export CSV" --file export.py --file tests/test_export.py \
  --ac "La première ligne contient les en-têtes" --test "python3 -m unittest" --dry-run
```

`quick` crée la branche `agentic/<id>` et son worktree (aussi avec `--dry-run`, qui ne
lance aucun agent : le retirer avec `git worktree remove`), génère un plan d'une PR, route
le modèle, lance l'agent puis les gates. Il ne commite, ne pousse ni ne fusionne rien : le worktree est laissé à l'orchestrateur, puis commits via
`agentic-commit.sh` et review indépendante. `delegate <plan.json>` fait de même pour un
plan PR_SPLIT à plusieurs unités ; les unités indépendantes tournent en parallèle.

## Configuration

`agentic.config.json` (modèle : `templates/agentic.config.json`, `$AGENTIC_CONFIG` ou
`--config` pour un autre chemin ; en LOCAL il reste sous `.agentic-local/`, hors Git).

- `models` : `id`, `harness`, `model`, `max_level` ou `tiers`, `efforts`, `cost_rank`
  (rang relatif fourni par vous, jamais un prix), `enabled` facultatif. Un modèle dont le
  binaire est absent du `PATH` n'entre pas dans l'inventaire.
- `harnesses` : presets `claude`, `codex`, `opencode`, ou `{"argv": [...]}` avec les
  jetons `{prompt}`, `{model}`, `{effort}`, `{worktree}` pour tout autre CLI. `extra_args`
  et `env_passthrough` sont facultatifs. Le niveau d'effort n'est transmis que par `codex`.
- `gates` : `commands` (argv, jamais un shell), `timeout`, `require_tests`, `size`.
- `run` : `timeout_seconds`, `max_turns`, `allowed_tools` (Claude).

Le routeur choisit le `cost_rank` le plus bas capable du niveau requis (voir
[MODELS](MODELS.md)). Presets vérifiés sur la documentation des CLI le 2026-11-07 ; les
tests utilisent un faux harnais, aucun appel réel à Claude, Codex ou OpenCode n'a été fait.
Les options changent entre versions : surcharger avec `argv` si besoin.

## Brief, handoff, gates

Le brief contient l'objectif, les critères, la **liste exhaustive des fichiers**, les
commandes exactes, les interdits et les skills sélectionnés. L'agent répond par un bloc
`handoff` JSON (statut, résumé, fichiers, tests, blockers). Cette réponse est une
déclaration : seules les gates décident. Sans bloc valide, la tâche reste COMPLETED si le
processus a réussi, et les gates tranchent.

| Gate | Échec quand |
|---|---|
| `scope` | un chemin modifié (commité, indexé, dirty ou non suivi) n'est pas déclaré |
| `tests-present` | du code change sans test ajouté ou modifié |
| `test-integrity` | test supprimé, `skip`/`xfail`/`only` ajouté (avertissement si moins d'assertions) |
| `secrets` | clé AWS/GitHub/Slack ou clé privée dans les lignes ajoutées |
| `size` | avertissement au-delà de 3 fichiers / 100 lignes ; `"mode": "fail"` pour bloquer |
| `commands` | une commande échoue, expire ou modifie l'arbre ; ignorées si une gate a échoué |

PASS prouve des propriétés mécaniques du diff, pas les critères d'acceptation : la review
indépendante reste obligatoire. Les commandes ne doivent pas écrire dans l'arbre hors
fichiers ignorés par Git. `--accept` n'accepte une tâche que sur PASS, pour libérer ses
dépendants ; ce n'est jamais une autorisation de merge.

## Escalade

Un échec ne relance jamais un modèle plus cher de lui-même. L'orchestrateur analyse, puis
enregistre la tentative :

```bash
python3 scripts/agentic-run.py attempt --task-id csv-export --outcome FAIL --level MEDIUM \
  --diagnosis-kind capacity --diagnosis "n'a pas su raisonner sur les cas limites"
```

Seul un diagnostic `capacity` fait monter d'un niveau au prochain `delegate`. Un échec sans
diagnostic bloque, comme dans [MODEL_ROUTING](MODEL_ROUTING.md).

## Garanties et limites

- L'agent n'est lancé qu'après validation du reçu : il reste en lecture seule jusqu'alors.
- Identité observée = PID d'un processus enfant créé ici, non authentifié. Runtime `process`.
- L'environnement transmis est filtré (clés du harnais seulement) ; ce n'est pas un bac à
  sable. Pour un modèle non fiable, exécuter dans un conteneur sans secrets.
- Jetons et coût ne sont connus que si le harnais les expose (JSON de Claude) ; sinon `null`.
  Chaque run ajoute une ligne à `runs.jsonl`, avec `brief.md` et les logs, dans
  `<git-common-dir>/agentic-runs/` (hors Git).
- Aucun worktree n'est supprimé automatiquement.

## Vérification automatique

`gates.commands: "auto"` (défaut) : `scripts/agentic-detect.py` lit les scripts déclarés
(package.json, pyproject, go.mod, Makefile…) et choisit par unité les commandes de son
profil (front, back, données, contrat) ; ticket doc seule : aucune commande requise. Rien
n'est inventé : commande absente = signalée, à fournir dans la config ou le plan.
`agentic-prepare.py init|check|units` prépare PREPARE depuis les fichiers visés.

## Tests métier avant l'implémentation

Le ticket établit RM et AC depuis les attentes explicites du demandeur ou les sources
métier. Définir les scénarios/tests de chaque règle ; `agentic-prepare.py check` vérifie
leur traçabilité. Ne pas inventer d'attente métier.

Avant le code, l'agent affecté écrit les tests métier du périmètre, sans code produit.
Pas d'échec initial, cycle rouge/vert, commit rouge ou review du rouge obligatoires.
Consigner l'état initial si les tests sont exécutables sur le code existant. Transmettre
tests, règles, AC et échecs préexistants à l'implementer pour guider son code. Protéger
les tests ; revoir avec l'orchestrateur tout changement d'attente métier. Verify exécute
les tests et contrôles pertinents.

Le défaut installé est `run.tdd.enabled: false`. Le cycle TDD en deux phases (`true`,
`--review-red`, `--green-only`) reste disponible sur demande explicite du ticket/projet.
