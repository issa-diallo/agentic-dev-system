# Plan — #6

PLAN: PASS. Research/Design PASS, architecture compatible, aucun blocker.

## Budget et délégation
Complexité élevée ; pas de métrique quota fiable ni plafond promis.
Orchestrateur : décisions et intégration ; implementer dédié : tous changements
fonctionnels dans ce worktree, séquentiellement ; reviewer indépendant lecture seule.
Outils : filesystem/Git/Bash/Python ; aucun installateur distant.

## Séquence
1. Alléger AGENTS, réutiliser docs/agentic/README pour navigation conditionnelle.
2. Créer MODELS et OPTIONAL_TOOLS ; enrichir CONTEXT, rôles et templates
   RESEARCH/PLAN/HANDOFF/VERIFY et aligner BOOTSTRAP/INSTALL/README/METHOD si utile.
3. Préserver en détail les obligations déplacées (architecture, états, sécurité,
   environnements) dans sources existantes ; aucune baisse de gate.
4. Installer STATUS neutre depuis templates/STATUS, préflight des nouvelles
   ressources obligatoires, checker de présence étendu sans prétendre gate PASS.
5. Tests de liens et contrats, génération petit LIGHT et multi-app LARGE,
   trois modes, personnalisation, aucune activation tierce, statut neutre.
6. Verify puis reviewer indépendant ; corriger ses findings ; commits atomiques,
   push/PR vers main, CI, READY_FOR_HUMAN sans merge.

## Livrable et validations
Fichiers autorisés : AGENTS, README, docs/agentic (hors preuves historiques),
install-agentic.sh, scripts/agentic-check.sh, tests, workflow existant si requis.
Ne modifier ni COMMITS ni la stack, ni configuration Codex globale.
Commandes : bash -n ; python3 -m unittest discover -s tests -v ; git diff --check.
Mesures : octets/lignes avant/après et scénario documentaire reproductible.
Rollback : revert commits, comparer les installations sans écraser les notes.

Verdict : PASS

## Complément — communication native
Plan PASS, aucun blocker, architecture/ADR inchangés. Complexité faible.
1. Étendre AGENTS et CONTEXT, actualiser décisions 08/09 sans installer d'outil.
2. Ajouter contrôle du contrat de communication et vérifier héritage avec les
   six générations existantes ; ne modifier aucun template de phase.
3. Reviewer indépendant : conformité des neuf règles, exemples terminé/partiel/
   bloqué et maintien d'un rapport structuré ; tests, diff, preuves et mesures.
4. Commit Gitmoji lié à #6, même PR #7, CI puis READY_FOR_HUMAN sans merge.
Orchestrateur implémente ce complément documentaire cadré ; reviewer distinct.
Pas de service, plugin, MCP, package ni configuration utilisateur modifiés.
