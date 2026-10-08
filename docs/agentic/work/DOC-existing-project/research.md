# Research — DOC-existing-project

Mode : LIGHT. Demande : ajouter une entrée projet existant sans documentation produit.

Research : PASS.

Inspection : AGENTS.md, METHOD, WORKFLOW, SCALING, STATUS, BOOTSTRAP,
README, template Research, installateur et agentic-check.
Le checker exige tous les documents produit. L’installateur copie des templates,
qui ne constituent pas des décisions validées. Aucun document produit/ADR local.
Pas de changement de stack, données, secrets ou action externe.
Risque : permettre un contournement des gates ou bloquer un ticket par un template vide.

## Extension installation locale

Research PASS : le mkdir prématuré provoque le refus initial. Les chemins racine
peuvent appartenir à l’équipe ; installer --local dans .agentic-local et utiliser
Git pour résoudre info/exclude, y compris dans un worktree. Pas de modification
automatique de AGENTS.md existant ; activation par prompt explicite.
