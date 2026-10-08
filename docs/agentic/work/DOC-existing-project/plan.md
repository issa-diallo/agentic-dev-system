# Plan — DOC-existing-project

Plan : PASS. Aucun blocker. Architecture existante conservée.

1. Ajouter EXISTING_PROJECT.md avec conditions, preuves et prompt de démarrage.
2. Aligner AGENTS, README, METHOD, WORKFLOW, SCALING, STATUS, BOOTSTRAP
   et le template Research ; clarifier les messages de l’installateur.
3. Ajouter --existing au checker sans modifier son défaut.
4. Vérifier syntaxe shell, liens et fixtures : existant sans produit accepté,
   socle incomplet refusé, produit incomplet refusé, produit complet accepté.
5. Review indépendante puis handoff. Pas de commit/PR sans ticket GitHub associé.

Exception : évolution ciblée de la méthode, pas nouveau produit ni gros périmètre ;
les phases produit ne sont pas rejouées. Worktree : /tmp/agentic-existing-project.

## Extension autorisée : correction et PR

Plan PASS : réécrire le contrôle préalable de l’installateur ; documenter les
trois modes, la priorité des règles équipe et l’activation explicite locale ;
ajouter des tests shell/Python standard library sur dépôts temporaires, dont
worktrees et collisions ; review indépendante puis commit lié au ticket et PR.
Le défaut de l’installateur entre désormais dans le périmètre.
