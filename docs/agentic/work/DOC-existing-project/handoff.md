# Handoff — #4 / DOC-existing-project

Méthode projet existant et installation personnelle locale réunies dans la PR.
PRODUCT conserve les templates produit ; EXISTING les omet ; LOCAL isole la
méthode sous .agentic-local et ajoute uniquement une exclusion Git locale.
Activation par prompt explicite, règles équipe prioritaires. FORCE est refusé ;
les mises à jour exigent comparaison et sauvegarde manuelles.

Le défaut préexistant d’installation fraîche est corrigé par le contrôle des
collisions avant mkdir. Les artefacts de story du dépôt source ne sont pas copiés.

Research, Design, Plan, Execute et Verify PASS. Voir review.md pour review.
Branche docs/existing-project ; worktree /tmp/agentic-existing-project.
Issue : https://github.com/issa-diallo/agentic-dev-system/issues/4
Ship limité au commit/push et à l’ouverture de PR demandés ; pas de merge.
Rollback du changement : revert du commit. Les installations locales existantes
restent à gérer manuellement, sans suppression automatique des notes personnelles.
