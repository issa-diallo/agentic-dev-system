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
