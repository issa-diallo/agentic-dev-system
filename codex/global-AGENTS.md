# Méthode agentic-dev-system (global)

Si le dépôt courant contient `.agentic-local/AGENTS.md`, lis-le intégralement, ainsi que
`.agentic-local/docs/agentic/LOCAL.md`, avant toute action.

- Avant tout BUILD non trivial, exécute la gate PR_SPLIT
  (`.agentic-local/docs/agentic/PULL_REQUESTS.md`).
- Une capacité autonome = un sous-ticket = une PR ; des capacités séparables
  regroupées rendent BUILD BLOCKED.
- Aucun ticket, branche, commit, push ni PR avant approbation du découpage.
- Commits via `agentic-commit.sh`. Sans `.agentic-local/`, ignore ce fichier.
