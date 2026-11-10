# Délégation à des modèles économiques

Cadrage/revue séparés de l’implémentation déléguée. Outils stdlib :

| Script | Rôle |
|---|---|
| `agentic-run.py` | route le modèle, lance le harnais CLI, applique les gates, enregistre les tentatives |
| `agentic-brief.py` | rend le brief fermé et lit le handoff structuré |
| `agentic-gates.py` | gates déterministes sur le diff, sortie prête pour `scheduler accept` |
| `agentic-claude.sh` | lance Claude Code avec les rôles de `claude/agents/` (équivalent de `agentic-codex.sh`) |

## Démarrage

```bash
cp docs/agentic/templates/agentic.config.json agentic.config.json   # racine de la méthode
python3 scripts/agentic-run.py inventory                            # modèles réellement disponibles
python3 scripts/agentic-run.py quick --id csv-export \
  --objective "Ajouter l'export CSV" --file export.py --file tests/test_export.py \
  --ac "La première ligne contient les en-têtes" --test "python3 -m unittest" --dry-run
```

`quick` crée branche `agentic/<id>`, worktree et plan, route, lance puis vérifie.
`--dry-run` crée le worktree sans lancement ; retrait : `git worktree remove`.
Ni commit, push ou merge : l'orchestrateur garde le worktree, commite via
`agentic-commit.sh` et obtient une review indépendante. `delegate <plan.json>`
traite le plan PR_SPLIT, unités indépendantes en parallèle.

## Configuration

`agentic.config.json` (modèle : `templates/agentic.config.json`, `$AGENTIC_CONFIG` ou
`--config` pour un autre chemin ; en LOCAL il reste sous `.agentic-local/`, hors Git).

- `models` : `id`, `harness`, `model`, `max_level` ou `tiers`, `efforts`, `cost_rank`
  (rang relatif fourni par vous, jamais un prix), `enabled` facultatif. Un modèle dont le
  binaire est absent du `PATH` n'entre pas dans l'inventaire.
- `harnesses` : presets `claude`, `codex`, `opencode`, ou `{"argv": [...]}` avec les
  jetons `{prompt}`, `{model}`, `{effort}`, `{worktree}` pour tout autre CLI. `extra_args`
  et `env_passthrough` sont facultatifs. L'effort passe par `codex` ou le jeton `{effort}`.
- `gates` : `commands` (argv, jamais un shell), `timeout`, `require_tests`, `size`.
- `run` : `timeout_seconds`, `max_turns`, `allowed_tools` (Claude).

Le routeur choisit le `cost_rank` le plus bas capable du niveau requis (voir
[MODELS](MODELS.md)). Presets : documentation CLI vérifiée le 2026-11-07 ; tests sur faux harnais sans
inférence réelle. Options variables selon version ; surcharge `argv` possible.

`run.subscription_only: true` : sans clé/endpoint/proxy, login abonnement sinon
BLOCKED. Quota épuisé : sans relance. Quota/dépassement payant (à désactiver) :
`not_verified`. Binaire PATH. Claude : Linux natif (managed et fragments JSON),
autres OS bloqués. Défaut `false`.

Double analyse HIGH/EXTRA_HIGH optionnelle : [contrat](DOUBLE_ANALYSIS.md).

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

- Reçu confirmé avant libération ; PID observé, runtime `process`.
  Environnement filtré, pas de sandbox ; conteneur pour modèle non fiable.
- `routing_policy` active le routage par `routing.role/phase` de chaque unité
  (défaut implementer/BUILD). Preuves `model_execution` : sélection, demande,
  transmission, observation/application, harnais, fournisseur déclaré, PID,
  sessions runtime/CLI distinctes et provenance. Voir [MODELS](MODELS.md).
- Effort imposé non transmissible : BLOCKED sans fallback. Lecture seule :
  preset Codex non modifié requis. Politique changée : réconciliation sans relance.
- Brief, logs et `runs.jsonl` : `<git-common-dir>/agentic-runs/`, hors Git.
  Tokens/coût absents : null. Aucun worktree supprimé automatiquement.

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

Défaut : `run.tdd.enabled: false`. TDD explicite (`true`, `--review-red`,
`--green-only`) facultatif.
Flux optionnel : [missions](WORKFLOW.md#missions-successives-dune-pr-préparée).

## Cycle de revue corrective borné

[Option : revue, corrections, budgets](REVIEW_CYCLE.md).
