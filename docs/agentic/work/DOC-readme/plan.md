# Plan — DOC-readme

Plan PASS après Design ; complexité faible, aucun blocker.
Réécrire README uniquement, garder les templates et scripts inchangés.
Vérifier les liens avec la suite existante, puis revue indépendante du contenu.
Branche docs/readme-overview, worktree /tmp/agentic-readme ; orchestrateur écrit,
reviewer distinct en lecture seule. Commit Gitmoji lié à #6, PR de suivi puisque
#7 est fusionnée. Retour arrière : revert du commit documentaire.

Plan PASS : clarifier l'introduction et insérer utilité/isolation avant les détails
de méthode. README et preuves uniquement ; liens, review et CI dans la même PR #8.

## Extension — Lead Tech de PR
Plan PASS, aucun blocker, architecture portable inchangée. Complexité moyenne.
Mettre à jour README, profil REVIEWER et orchestration, renvoi AGENTS/index,
WORKFLOW Ship et métadonnées templates REVIEW/SHIP ; pas de nouvelle phase.
Tester contrat et copies héritées avec suite existante ; revue indépendante.
Fournir un prompt portable exécutable par délégation quand le harness le permet,
sans imposer de nom de modèle ni prétendre activer un bot GitHub. PR #8 sans merge.
