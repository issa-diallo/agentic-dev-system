# Plan — DOC-architecture-fast

PLAN: PASS

1. Remplacer les templates Architecture et ADR par des contrats courts.
2. Aligner README, AGENTS, METHOD, WORKFLOW, SCALING, EXISTING_PROJECT,
   BOOTSTRAP, INSTALL, OPTIONAL_TOOLS, index et modèles Research/Plan/Verify
   ainsi que les rôles Reviewer et Orchestrator.
3. Ajouter des contrôles de non-régression des contrats documentaires et de
   leur héritage ; exécuter la suite unittest, syntaxe shell et diff --check.
4. Faire relire le diff par un agent indépendant en lecture seule.

Fichiers : ceux listés ci-dessus, tests/test_context.py et artefacts de cette story.
Risques : règles contradictoires, validations différées perdues, suppression
accidentelle de protections ; mitigations par registre explicite et review.
Pas d’ADR : aucun choix technique structurant du logiciel modifié.

Worktree : /tmp/agentic-architecture-fast ; branche docs/architecture-fast.
Environnement : Python 3 et Bash disponibles, aucune dépendance à installer,
aucun port/service/base partagé. Setup = git worktree add ; dev = édition docs ;
test = python3 -m unittest discover -s tests -v ; arrêt = aucun service.
Un seul écrivain. Reviewer indépendant après Verify, lecture seule.
Niveau recommandé Medium pour documentation ; modèle courant conservé.
Quota/coût non observables. Arrêt : critères vérifiés et review sans Major/Critical.
