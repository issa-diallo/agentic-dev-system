# Verify — #6

VERIFY: PASS — 2026-10-08, worktree /tmp/agentic-codex-context,
branche feat/codex-context, base 20a2e1b. Vérifications relancées par orchestrateur puis reviewer indépendant après correction.

| Critère | Preuve | Résultat |
|---|---|---|
| AC1 gates/sécurité/Gitmoji | AGENTS + METHOD/WORKFLOW + test_root_invariants_and_size ; COMMITS inchangé ; revue sémantique indépendante requise | PASS statique |
| AC2 navigation/modèles/compaction | liens source/générés, CONTEXT 26 décisions, MODELS, HANDOFF | PASS |
| AC3 rôles | trois contrats et Plan, orchestration/implémentation/review séparés | PASS |
| AC4 héritage | six générations PRODUCT/EXISTING/LOCAL × LIGHT/LARGE, règles API/web, STATUS neutre, preuves source exclues | PASS |
| AC5 outils | OPTIONAL_TOOLS huit axes par outil ; aucune configuration tierce générée | PASS documentaire |
| AC6 tests/mesures | commandes ci-dessous ; revue indépendante suivante | PASS local |
| AC7 publication | PR #7 et CI PASS, voir ship.md | PASS |

## Commandes exactes

- `bash -n install-agentic.sh scripts/agentic-check.sh` : exit 0.
- `python3 -m unittest discover -s tests -v` : 17 tests PASS, 4,225 s lors de la revalidation indépendante finale.
- `git diff --check` : exit 0.
- `wc -c -l AGENTS.md` : 3 840 octets, 63 lignes.
- Baseline `git show origin/main:AGENTS.md` : 8 764 octets, 327 lignes.

Les scénarios négatifs retirent chaque ressource obligatoire et vérifient le
refus avant écriture en trois modes ; tests historiques couvrent collisions,
symlinks, exclusions Git, worktree, FORCE et options invalides.
CI existante exécute syntaxe et découverte unittest, donc inclut les nouveaux tests.
Build/API/browser sans objet pour cette méthode Bash/Markdown.

## Mesures initiales et limites

Différence AGENTS : -4 924 octets (-56,2 %), -264 lignes. Mesure de texte statique,
pas mesure du contexte total ni économie de tokens/quota. Le corpus détaillé
s'enrichit ; le bénéfice dépend de la sélection effective des lectures.
Les fixtures LIGHT/LARGE testent l'installation et la personnalisation ; elles
ne construisent pas des applications complètes ni n'exécutent un modèle.
Liens Markdown inline locaux vérifiés ; URLs distantes, anchors et obéissance
runtime non certifiés par ce test. Aucun benchmark tiers exécuté.
Tokens, quota, lectures effectives/redondantes : non observables dans ce test.

Verdict local : PASS. Review et publication restent des gates distincts.

## Boucle de review

Le reviewer a reproduit une exposition de STATUS en LOCAL lorsque STATUS source
est absent et que les règles équipe réincluent la destination générée. Correction :
contrôle explicite de cette destination avant copie ; test de refus et restauration
exacte des exclusions, puis succès sans négation. Inventaire de test indépendant,
parité des listes, ordre complet des phases et copies exactes également vérifiés.
Review finale : PASS, aucun finding ouvert.

## Complément — communication native

Verify PASS. 18 tests PASS (reviewer : 4,174 s), syntaxe Bash PASS et
`git diff --check 7c9afec` PASS. Le contrat natif est présent et les six générations
copient AGENTS/CONTEXT exactement. Aucun changement des templates de phase,
du workflow ou de l'installateur dans ce complément (diff depuis 7c9afec vide
pour ces chemins). Aucun outil, plugin, MCP ou package ajouté.

Mesure finale : AGENTS 5 044 octets / 85 lignes, contre 8 764 / 327 initialement
(-42,4 % en octets). Le complément ajoute 1 204 octets d'instructions universelles
explicitement demandées ; aucun gain de tokens de sortie mesuré.

### Probes qualitatives du reviewer

Scénarios synthétiques, pas des résultats applicatifs réels :
- Terminé, documentation et 18 tests fournis : réponse en deux sections,
  Résultat puis Validation ; aucune section vide ni action inventée.
- Partiel, unitaires réussis, intégration impossible sans identifiants : réponse
  conserve « non exécutés », raison, risque de régression et validation manquante ;
  prochaine étape avec accès aux identifiants par mécanisme sécurisé.
- Review structurée demandée, Major de fuite tenant non corrigée : format REVIEW
  conservé (inputs, findings, AC, architecture/sécurité, evidence, conclusion),
  verdict CHANGES_REQUIRED ; aucune preuve, localisation ou exécution inventée.

Les probes vérifient ponctuellement concision, informations critiques et exception
pour un rapport complet. Elles ne garantissent pas le comportement de chaque
modèle/session. Les tests automatiques valident contrats et héritage statiques.
