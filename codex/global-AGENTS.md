# Méthode agentic-dev-system (global)

Si le dépôt courant contient `.agentic-local/AGENTS.md`, lis-le intégralement, ainsi que
`.agentic-local/docs/agentic/LOCAL.md`, avant toute action.

- Avant tout BUILD non trivial, exécute la gate PR_SPLIT
  (`.agentic-local/docs/agentic/PULL_REQUESTS.md`).
- Une capacité autonome = un sous-ticket = une PR ; des capacités séparables
  regroupées rendent BUILD BLOCKED.
- Consigne le plan validé dans `.agentic-local/docs/agentic/work/<ticket>/pr-split.json`
  (une PR par entrée, avec sa `branch` et ses `files`) : le hook pre-push refuse
  sinon de pousser la branche.
- L’orchestrateur valide le découpage selon PR_SPLIT, avec review indépendante
  lorsque requise, sans approbation humaine systématique. Aucun sous-ticket,
  branche, commit, push ni PR avant cette validation. Les gates et autorisations
  applicables aux actions suivantes restent obligatoires.
- Commits via `agentic-commit.sh`. Sans `.agentic-local/`, ignore ces règles, sauf `agentic ?`.
- Si le message de l'utilisateur est exactement `agentic ?` : lis `.agentic-local/AGENTS.md`
  et `.agentic-local/docs/agentic/LOCAL.md` si ce n'est pas déjà fait, et vérifie que le fichier
  `git rev-parse --git-path hooks/pre-push` contient « agentic-dev-system push guard ».
  Si tout est bon, réponds exactement « Agentic Dev System prêt à commencer. » sans rien ajouter. Sinon réponds
  « Agentic Dev System NON prêt : » suivi de ce qui manque.
