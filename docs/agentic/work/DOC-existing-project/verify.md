# Verify — #4 / DOC-existing-project

Verify : PASS.

- `bash -n install-agentic.sh scripts/agentic-check.sh` : exit 0.
- `git diff --check` : exit 0.
- `python3 -m unittest discover -s tests -v` : 10 tests PASS, dépôts Git temporaires.
- Installation PRODUCT fraîche et contrôle de présence : PASS.
- EXISTING sans documents produit et contrôle de présence : PASS.
- LOCAL : règles équipe inchangées, git status inchangé, exclusions conservées,
  deuxième installation refusée sans écrasement, contrôle de présence PASS.
- Worktree lié : installation et exclusion Git PASS.
- Collisions, symlink docs, chemin local suivi puis supprimé, FORCE, option
  inconnue, cible non Git et sous-dossier : refus vérifiés.
- Contrôle présence antérieur : six scénarios PASS (voir préparation).

Workflow GitHub ajouté pour syntaxe shell et tests. Résultat distant à consulter
sur la PR ; pas de build applicatif pour ce dépôt de scripts/documentation.

Review : régression ajoutée pour les négations .gitignore ; refus avant copie
et restauration byte-for-byte du contenu exclude vérifiés.
