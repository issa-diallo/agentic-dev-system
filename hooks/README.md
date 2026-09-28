# Safety Hooks

Ce dossier documente les hooks recommandés pour les agents compatibles.

## Pre-tool safety

Avant l'exécution d'un outil/commande :
- détecter les commandes destructrices ;
- bloquer ou demander validation ;
- protéger main/production ;
- empêcher les suppressions massives accidentelles.

Voir `docs/agentic/SAFETY.md`.

## Post-tool audit

Après les outils importants :
- journaliser l'action ;
- conserver le code de retour ;
- enregistrer les preuves utiles ;
- ne jamais journaliser de secrets.

## Portabilité

Les mécanismes de hooks diffèrent selon le harness (Codex, Claude, etc.).
Ce repo impose le comportement attendu, pas une implémentation propriétaire unique.
