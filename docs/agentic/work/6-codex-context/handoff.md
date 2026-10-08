# Handoff — #6 Codex context

IMPLEMENTATION_COMPLETE. Execute PASS ; Verify/Review indépendants PASS après correction ; publication et CI à effectuer.

## Résultat

AGENTS réduit de 8 764 octets / 327 lignes à 3 840 octets / 63 lignes.
Mesure statique `wc -c -l`, aucune équivalence tokens/quota revendiquée.
Index conditionnel, MODELS sans noms figés, CONTEXT avec les 26 décisions du
guide, OPTIONAL_TOOLS qualifié sans activation. Rôles et quatre templates
précisent contrats, recherche ciblée, preuve et reprise. METHOD/WORKFLOW
conservent détails architecture, états, isolation et DoD complète.

Installation : STATUS initialisé depuis template neutre, work exclu, préflight
de toutes ressources obligatoires avant écriture. Checker de présence étendu,
sans prétendre vérifier les gates ou l’obéissance du modèle.

## Fichiers

AGENTS.md, README.md ; docs/agentic/{README,METHOD,WORKFLOW,MODELS,CONTEXT,
OPTIONAL_TOOLS,INSTALL,BOOTSTRAP}.md ; les trois roles ; templates/{PLAN,
HANDOFF,RESEARCH,VERIFY,STATUS}.md ; install-agentic.sh ; scripts/agentic-check.sh ;
tests/test_context.py. COMMITS et preuves de préparation inchangés.

## Commandes et résultats

Dans /tmp/agentic-codex-context, branche feat/codex-context, 2026-10-08 :

| Commande | Résultat |
|---|---|
| bash -n install-agentic.sh scripts/agentic-check.sh | PASS |
| python3 -m unittest discover -s tests -v | PASS, 17 tests dont les 10 existants |
| git diff --check | PASS |
| wc -c -l AGENTS.md | 63 lignes, 3 840 octets |

Nouveaux tests stdlib : liens Markdown locaux source/générations ; invariants
racine et 26 conseils ; 6 installations modes × échelles ; personnalisation
multi-app préservée ; absence configurations tierces ; template STATUS neutre ;
checker refusant ressource manquante ; chaque source obligatoire retirée tour à
tour, dans les trois modes, refus sans modification des fichiers cible/Git.

## Limites et reprise

Tests statiques et installateur réels, aucune session de modèle exécutée.
Compatibilité outils tiers documentaire, aucune installation ni benchmark.
Nombre réel de fichiers lus par Codex, lectures redondantes, quota et tokens
non mesurés ; seuls tailles et contrats statiques sont prouvés ici.
À la remise par l’implementer : aucun commit/push. Pas de changement de stack ou de scope. Aucun blocker.
Verify et review indépendante des invariants et du diff sont terminés ;
prochaine action : publier PR/CI selon autorisation. Mission PR seule :
READY_FOR_HUMAN ; DONE exige merge et cleanup. Aucun merge autorisé ici.
