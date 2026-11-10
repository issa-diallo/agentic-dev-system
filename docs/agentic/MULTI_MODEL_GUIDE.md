# Un ticket, deux abonnements, zéro API à l'usage

Ce guide prépare une activation volontaire des CLI officielles Codex et Claude
Code. Deux abonnements restent nécessaires ; « zéro API à l'usage » désigne le
chemin d'inférence autorisé, pas une mesure de facture ni une garantie de quota.
Les recettes automatisées utilisent des CLI factices. Aucun essai réel des deux
abonnements, des images ou de MCP n'est attesté par ce guide.

## Installer et vérifier les comptes

Le mode `subscription_only` actuel exige Linux natif pour Claude, Python 3.11+
pour lire les configurations Codex, Bash et Git. macOS, Windows et WSL restent
bloqués pour Claude tant que leur chaîne complète de politiques n'est pas
contrôlée, même si les CLI elles-mêmes y sont installables.

Installer depuis les sources officielles, puis conserver localement les versions
et l'origine des exécutables. Le runner utilise les binaires du `PATH` ; il ne
vérifie pas leur signature ni leur provenance.

```bash
curl -fsSL https://chatgpt.com/codex/install.sh | sh
curl -fsSL https://claude.ai/install.sh | bash
command -v codex
command -v claude
codex --version
claude --version
codex login
codex login status
claude auth login
claude auth status --json
```

Choisir la connexion ChatGPT pour Codex et le compte claude.ai de l'abonnement
Claude. Le contrôle attend `Logged in using ChatGPT` côté Codex ; côté Claude,
`loggedIn: true`, `authMethod: "claude.ai"` et `apiProvider: "firstParty"`.
Un abonnement ou modèle absent reste un blocage, jamais une invitation à créer
une clé API. Les détails d'identité des sorties de login restent locaux.
Sources officielles consultées le 2026-11-10 : [installation Codex](https://learn.chatgpt.com/docs/codex/cli),
[authentification Codex](https://learn.chatgpt.com/docs/auth),
[installation Claude](https://code.claude.com/docs/en/setup) et
[authentification Claude](https://code.claude.com/docs/en/authentication).

Avant toute inférence, désactiver dans les comptes les dépassements payants,
recharges et usages supplémentaires. Vérifier localement l'absence de clés,
endpoints, proxies et redirections d'authentification dans l'environnement et les
configurations utilisateur, projet et administrateur. Ne pas afficher leurs
valeurs ni recopier les fichiers de credentials dans un ticket ou un log partagé.
Le runner refuse les entrées de facturation/redirection qu'il contrôle, y compris
`OPENAI_*`, `ANTHROPIC_*`, `CLAUDE_CODE_OAUTH_TOKEN`, proxies et helpers d'API.
`quota` et `overage` restent `not_verified` : le login ne prouve pas leur état.
Ce contrôle n'est pas une sandbox : les commandes du projet, outils et MCP
peuvent avoir leurs propres coûts et accès, à qualifier avant de les autoriser.

**Analyses et reviews Claude sur abonnement.** Le preset isolé utilise
`--safe-mode`, qui conserve l'authentification native, avec les outils désactivés,
MCP strict vide, `dontAsk`, sources de settings vides, commandes/skills désactivés,
`disableAllHooks: true` et aucune persistance de session. `--bare` n'est pas utilisé :
ce mode ignore la connexion abonnement. Une version CLI qui ne reconnaît pas
`--safe-mode` échoue explicitement, sans relance moins isolée.

Le safe mode conserve toutefois certaines politiques administrateur. Pour ne pas
exécuter de hooks ou de helpers managed, cette exception refuse avant le probe
d'authentification toute source managed Linux ou cache `~/.claude/remote-settings.json`
non vide, illisible ou malformé. Les objets JSON vides sont permis. Elle exige ensuite
un plan personnel vérifié `pro`, `max` ou `ultra` ; Team, Enterprise et plan inconnu
restent BLOCKED car leurs politiques distantes peuvent être chargées après le
contrôle local. Ces restrictions concernent seulement les analyses/reviews isolées,
pas l'implémentation Claude ni les missions Codex.
Sources : [CLI](https://code.claude.com/docs/en/cli-reference),
[hooks managed](https://code.claude.com/docs/en/settings-reference#disableallhooks),
[politiques distantes](https://code.claude.com/docs/en/server-managed-settings#platform-availability).
Garder `double_analysis` et `review_cycle` désactivés jusqu'à un essai réel réussi
du preset exact avec chaque modèle voulu. Un login ou des tests factices ne prouvent
pas l'authentification du processus d'inférence.

## Configurer localement le routage

Installer la méthode suivant [INSTALL](INSTALL.md), puis travailler depuis la
racine du projet. Créer sans écraser de fichier existant
`.agentic-local/agentic.config.json`, exclu de Git ; vérifier l'exclusion avec
`git check-ignore .agentic-local/agentic.config.json`.
Le template générique ne configure pas à lui seul ce parcours à deux abonnements.

Voici un squelette à compléter, volontairement non lançable tant que les deux
champs `model` commencent par `<`. Remplacer les identifiants CLI seulement après
avoir vérifié leur accès dans chaque compte. Les `max_level` et `efforts` sont des
déclarations d'inventaire à qualifier, pas des capacités découvertes : réduire
les niveaux/efforts non vérifiés. Le minimum HIGH du reviewer demeure obligatoire.
`cost_rank` donne un ordre relatif choisi par l'opérateur, sans prix associé.

```json
{
  "version": 1,
  "models": [
    {"id": "codex-account", "harness": "codex", "provider": "openai",
     "model": "<modele-codex-verifie>", "max_level": "HIGH",
     "efforts": ["low", "medium", "high"], "cost_rank": 1,
     "modalities": ["text"]},
    {"id": "claude-account", "harness": "claude", "provider": "anthropic",
     "model": "<modele-claude-verifie>", "max_level": "MEDIUM",
     "efforts": ["low", "medium"], "cost_rank": 1,
     "modalities": ["text"]}
  ],
  "routing_policy": {"version": 1, "enabled": true, "rules": [
    {"id": "write", "match": {"role": "implementer"},
     "prefer": [{"model": "claude-account"}], "fallback": "blocked"},
    {"id": "tests", "match": {"role": "test-author"},
     "prefer": [{"model": "codex-account"}], "fallback": "blocked"},
    {"id": "review", "match": {"role": "reviewer"},
     "prefer": [{"model": "codex-account"}], "fallback": "blocked"}
  ]},
  "gates": {"commands": "auto", "require_tests": true},
  "run": {"subscription_only": true, "timeout_seconds": 1800,
    "missions": {"enabled": true}, "tdd": {"enabled": false},
    "double_analysis": {"enabled": false},
    "review_cycle": {"enabled": false}}
}
```

Ce choix illustre tests Codex, implémentation Claude, review Codex dans une session
distincte. Il ne classe pas les fournisseurs. Une tâche HIGH/EXTRA_HIGH bloquera
si l'inventaire ne contient pas de modèle/effort capable pour son rôle : étendre
l'inventaire et la politique uniquement après qualification, sans baisser le
niveau exigé. Les [règles de routage](MODELS.md) décrivent les autres rôles,
les overrides stricts et les efforts portables. L'effort est transmis par le
preset Codex ; le preset Claude actuel ne le transmet pas. Un effort explicitement
imposé à Claude bloque, et l'effort effectif reste non vérifié.

```bash
python3 .agentic-local/scripts/agentic-run.py inventory \
  --config .agentic-local/agentic.config.json
```

`inventory` vérifie la configuration et la présence des binaires, sans login ni
inférence. Il ne découvre ni les modèles accessibles, ni leurs modalités, ni le
quota. Pour un ticket, invoquer dans la session ayant chargé la méthode :

```text
$start-ticket https://github.com/organisation/depot/issues/numero
```

L'orchestrateur vérifie PREPARE, PR_SPLIT, worktree/owner, commandes Verify et
configuration avant de déléguer. Pour contrôler un plan déjà préparé sans agent :

```bash
python3 .agentic-local/scripts/agentic-run.py delegate \
  .agentic-local/docs/agentic/work/TICKET/pr-split.json --repo . \
  --config .agentic-local/agentic.config.json \
  --state .agentic-local/docs/agentic/work/TICKET/dry-state.json --dry-run
```

Le dry-run peut vérifier le login et écrire un état simulé ; il ne prouve ni
l'authentification du processus d'inférence, ni le modèle appliqué. Conserver cet
état comme preuve de simulation, séparé de l'état réel. Après la checklist et
l'autorisation applicable, l'orchestrateur utilise `delegate` sans `--dry-run`,
avec un chemin `--state` réel neuf et conservé pour les reprises.

## Capacités et preuves à conserver

| Élément | Ce que le parcours établit / limite |
|---|---|
| Texte et fichiers | Brief et chemins autorisés ; disponibilité des outils selon preset. Claude analyse/review reçoit les sources UTF-8 et le diff inline, sans lecture libre. |
| Images | `modalities` est déclaratif. Aucun transport automatique d'image dans ces briefs ni test réel attesté ; ne pas annoncer de support sans essai du CLI/modèle exact. |
| Outils et MCP | Aucun MCP pour les analyses/reviews Claude isolées. Ailleurs, présence d'une configuration ou support annoncé du CLI ne prouve ni accès ni exécution sûre ; essai explicite requis. |
| Modèle | `selected`, `requested` et `transmitted` diffèrent de `observed` et `applied`. Codex non observé reste `null` ; Claude expose parfois un seul modèle dans son JSON. Alias non résolus, plusieurs modèles non départagés. |
| Effort | Effort transmis distinct de l'effort observé ; ce dernier reste `null` faute de preuve. |
| Fournisseur et indépendance | Fournisseur déclaré par configuration ; identités PID/session runtime observées, session CLI si exposée. Deux fournisseurs ne prouvent pas deux sessions indépendantes. |
| Usage et quota | Usage/coût seulement si exposés, sinon `null`. Une estimation de coût CLI n'est pas la facture ; quota global et dépassement payant restent `not_verified`. |

Conserver hors Git le plan/hash, base/head/snapshot, choix de routage et son motif,
rôle/phase, fournisseur déclaré, modèle/effort demandé et observé, reçus, arrêts,
durée et usage disponibles. Les preuves actuelles se retrouvent dans l'état
scheduler (`model_routing`, `model_execution`, `mission_history`, `result`), le
rapport de `delegate` et `<git-common-dir>/agentic-runs/runs.jsonl`. Résoudre le
répertoire commun avec `git rev-parse --git-common-dir` depuis le worktree.
Le journal brut existant est par lancement ; il ne constitue pas un compteur
universel de tentatives ni un verdict métier. Le cycle de revue conserve ses
propres bornes persistantes. Une mesure absente reste `null`/non observable.
Briefs et sorties brutes peuvent contenir du contenu privé : ne pas publier ces
fichiers, credentials, prompts ou environnement pour justifier une PR.
Le [panneau facultatif](AGENT_PANEL.md) observe les agents, sans valider les gates.

## Recette simulée et essai réel avant activation

Depuis le dépôt source de la méthode, la CI exécute les mêmes tests stdlib :

```bash
python3 -m unittest discover -s tests -p test_subscription.py -v
python3 -m unittest discover -s tests -p test_missions.py -v
python3 -m unittest discover -s tests -p test_analysis.py -v
python3 -m unittest discover -s tests -p test_review_cycle.py -v
python3 -m unittest discover -s tests -v
```

Ces tests lancent des processus factices dans des worktrees temporaires et
couvrent le routage, les refus, l'indépendance et la reprise. Ils ne qualifient
pas le raisonnement des modèles ni les abonnements officiels.

Avant activation sur un projet, l'opérateur coche cette checklist seulement sur
preuves locales, sans credentials ni données sensibles. Aucun item n'est acquis
par une CI verte. L'essai réel est à effectuer avant activation des options.

- [ ] Versions, origine des CLI, OS, comptes abonnés et modèles accessibles notés ; login vérifié pour le preset exact, dépassement payant désactivé dans chaque compte.
- [ ] Configuration locale exclue, aucun chemin de facturation/redirection ; commandes/outils/MCP autorisés et non facturants vérifiés séparément.
- [ ] Ticket LOW : une mission ciblée, pas de double analyse ; contrôles adaptés et review indépendante de livraison conservés.
- [ ] Ticket MEDIUM : tests, implémentation, Verify puis review dans une session indépendante ; modèle/effort transmis confrontés aux observations disponibles.
- [ ] Ticket HIGH : niveau/effort capables vérifiés ; deux analyses seulement si justifiées et après essai réel du preset Claude `--safe-mode` sur abonnement personnel, sans politique managed ni cache distant non vide. Vérifier les deux reçus, avis et arbitrage sourcé avant le premier écrivain.
- [ ] Ticket EXTRA_HIGH : inventaire capable étendu après vérification, analyses indépendantes/arbitrage, protections du risque et seconde lecture Lead Tech distincte ; validation humaine applicable conservée.
- [ ] Pour chaque niveau, durée/tentatives/usage réellement exposés notés, valeurs absentes non inventées ; images/MCP marqués non vérifiés ou liés à un essai explicite par version/modèle/preset.
- [ ] Quota indisponible ou épuisé, avis absent, désaccord critique, mutation du plan ou timeout : BLOCKED sans fallback payant ; arrêt et ownership réconciliés avant reprise.
- [ ] PREPARE → BUILD → SHIP, PR_SPLIT, Verify, review, PR_SCOPE, CI et autorisation humaine du merge restent requis. Une sortie zéro n'est jamais un PASS métier.

La configuration de départ n'active ni double analyse ni revue corrective.
Après essai réel réussi, utiliser les contrats de [double analyse](DOUBLE_ANALYSIS.md)
et de [revue corrective](REVIEW_CYCLE.md), avec justification, arbitrage et bornes
de tentatives/corrections/rang explicites. Sans preuve d'accès abonnement en mode
isolé, ces options restent désactivées et leur recette réelle BLOCKED.

## Blocage, reprise et retour arrière

Conserver l'état, le plan, les preuves et le worktree. Confirmer l'arrêt réel
avant de libérer l'owner ; un timeout ou `COMPLETED` ne suffit pas. Reprendre
`delegate` avec les mêmes plan/configuration et `--state` : les missions finies
ne sont pas relancées aveuglément. Une mutation des entrées exige réconciliation
et revalidation ; un nouvel état ne doit pas effacer un échec pour forcer un PASS.
Les désaccords et risques critiques suivent l'arbitrage sourcé, sans faux consensus.
Toute correction retourne à l'implementer, puis Verify et review fraîches ; une
escalade exige le diagnostic de capacité prévu par [DELEGATION](DELEGATION.md).

Pour retirer l'activation, arrêter/réconcilier les missions actives puis restaurer
la configuration locale sauvegardée ou désactiver les options volontaires. Garder
les historiques ; ne pas supprimer les worktrees ni effacer les credentials.
Une PR s'arrête à `READY_FOR_HUMAN` après tous les gates et CI, sans fusion
automatique. L'activation et son retrait n'accordent aucune autorisation de merge.
