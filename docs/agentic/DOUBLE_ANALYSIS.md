# Double analyse optionnelle avant BUILD

Avec `run.missions.enabled: true` et `run.subscription_only: true`, activer :

```json
"double_analysis": {
  "enabled": true,
  "justification": "Deux avis nécessaires pour cette décision coûteuse à inverser",
  "arbitration_file": "/chemin/local/arbitrage.json"
}
```

Le défaut est désactivé. Seules les unités dont le niveau métier initial est
HIGH/EXTRA_HIGH ajoutent deux missions `explorer/PREPARE`, avant tout auteur de
tests ou implementer. LOW/MEDIUM restent inchangés ; le plancher HIGH du reviewer
ne déclenche pas cette option. TDD explicite et option active sont incompatibles :
BLOCKED explicite, sans contournement de la gate.

Chaque unité concernée fournit un contrat préparé, par exemple :

```json
"analysis": {
  "rules": [{"id": "RM1", "text": "Règle issue du ticket"}],
  "sources": [{"id": "S1", "path": "src/contrat.py"}]
}
```

Les AC du plan sont référencés `AC1`, `AC2`… dans leur ordre. Les règles et sources
ont des identifiants uniques. Sources explicites UTF-8, régulières, sans symlink,
confinées au worktree ; `.git`, `.agentic-local` et chemins `.env*` sont refusés.
Le bundle inline complet est borné à 60 000 octets ; préparer moins de sources
plutôt que les tronquer. Ne jamais déclarer un fichier contenant des secrets.
Les deux prompts sont identiques, sans avis du premier dans le second.

Le routeur choisit un modèle capable par preset officiel non modifié Codex puis
Claude, avec la politique configurée. Déclarer les deux dans l’inventaire ; aucun
fournisseur n’est déduit du nom du modèle. Politique contradictoire, fournisseur
absent, quota, timeout, avis manquant ou arrêt non confirmé : BLOCKED, aucun
fallback ni relancement automatique. Reçus, sessions, handoffs et arrêts restent
dans l’historique scheduler. Une sortie zéro ne remplace pas les deux avis.

Chaque `handoff.analysis` contient `bundle_sha256`, `decisions`, `risks` et
`assumptions`. Chaque entrée a `id`, `statement`, `rationale` et des listes non
vides `acceptance`, `rules`, `sources` référençant le contrat. Chaque avis couvre
tous les AC et règles et contient au moins une décision. Un risque ajoute
`severity` (`Critical/Major/Minor/Nit`), `status` (`open/mitigated`) et `mitigation`.
Les mitigations déclarées restent des arguments à vérifier par l’orchestrateur.

La synthèse expose les deux avis et leurs hash, accords et disputes par catégorie
et identifiant. Toute différence, même textuelle, exige arbitrage ; aucune mesure
de similarité ou moyenne. Un risque Critical ouvert bloque même avec deux avis
identiques. L’arbitrage local suit ce contrat :

```json
{"version":1,"units":{"PR-ID":{
  "bundle_sha256":"hash du rapport","opinions_sha256":["hash Codex","hash Claude"],
  "orchestrator_verified":true,"verdict":"PASS","resolutions":[{
    "dispute_id":"risks:R1","decision":"Choix retenu",
    "acceptance":["AC1"],"rules":["RM1"],"sources":["S1"],
    "rationale":"Motif lié aux critères et sources","mitigation":"Protection concrète"
  }]
}}}
```

Chaque dispute a exactement une résolution sourcée ; un risque critique ouvert
exige une mitigation non vide. `orchestrator_verified` est une attestation de la
frontière de confiance, pas une authentification ni une validation sémantique.
Conserver cet arbitrage hors Git. Après édition, reprendre `delegate` avec le même
plan/configuration/`--state` : seuls les blocages d’arbitrage se lèvent automatiquement,
sur avis, sources, HEAD, plan et snapshot inchangés.
Les sources sont relues avant le premier writer, y compris celles ignorées par
Git, jusqu’au handshake de lancement. La consommation de la gate est liée au reçu
observé et à l’autorisation du premier writer ; elle reste dans l’état et son
historique après `requeue`, sans être déduite rétroactivement d’une ancienne sortie.
Les mutations tests/produit autorisées après ce reçu ne périment pas l’analyse
du même contrat. Une interruption peut être réconciliée explicitement par `requeue`
si contrat et preuves sont toujours valides ; la reprise seule n’est pas un défaut.

Plan, périmètre, AC/RM, définitions des sources, HEAD de base et empreinte de
politique/configuration restent liés immuablement aux avis, même après consommation.
Avant le premier writer, snapshot et contenu des sources doivent aussi être
inchangés. `requeue` ne réhabilite jamais un ancien consensus sur de nouveaux inputs :
le résultat courant devient `BLOCKED`/`stale`, avec le verdict historique conservé.
Conserver l’état et les preuves, confirmer arrêt/ownership, révalider PREPARE et le
contrat puis orchestrer explicitement de nouvelles analyses dans une nouvelle
mission/état. Aucun reset, effacement d’historique ou relancement automatique ne
remplace cette réconciliation ; un arbitrage ne répare pas des inputs périmés.

Codex conserve sa sandbox `read-only`. Claude reçoit uniquement le bundle, sans
outil intégré/MCP, commande, hook, plugin ou contexte découvert automatiquement
(`--bare`, `--tools ""`, MCP strict vide, `dontAsk`, session neuve). Cette exception
est limitée à l’analyse ; les reviewers Claude restent refusés. Ces protections
reposent sur le CLI officiel de confiance, sans sandbox OS ajoutée. Options
vérifiées dans la [référence Claude Code](https://code.claude.com/docs/en/cli-reference)
le 2026-11-09 ; CLI ne supportant pas ces options : échec explicite. Les tests
utilisent de faux CLI, ne prouvent pas le raisonnement des modèles. Modèle/effort
effectifs non exposés restent null ; quota et dépassement payant non vérifiés.
Cette gate ne remplace aucun Verify, review indépendante, PR_SCOPE, CI ou SHIP.
