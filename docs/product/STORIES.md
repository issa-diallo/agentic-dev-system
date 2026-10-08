# Stories — Optimisation Codex

STORIES: PASS

## S01 / #6 — Hériter d'une méthode ciblée et vérifiable
En tant que mainteneur, je veux que chaque installation reçoive les règles de
contexte et de délégation afin de réduire les lectures inutiles sans perdre les gates.

Critères :
- AC1 : toutes les phases, DoR/DoD, sécurité et Gitmoji conservés et accessibles.
- AC2 : AGENTS réduit ; index conditionnel ; modèles sans noms figés ; compaction.
- AC3 : rôles Orchestrator, Implementer et Reviewer avec entrées/sorties, outils, périmètre, niveau et validation.
- AC4 : héritage identique en LIGHT et LARGE, règles locales conservées, modes
  PRODUCT/EXISTING/LOCAL préservés ; preuves source non distribuées.
- AC5 : RTK, QMD, Headroom et Ponytail évalués : intérêt, compatibilité Codex,
  dépendances, sécurité, cache, limites des mesures, désinstallation et maintenance, désactivés par défaut et réversibles.
- AC6 : tests, liens, CI et revue indépendante ; mesures en octets sans tokens inventés.
- AC7 : commits Gitmoji liés à #6 et PR vers main, sans merge.

Dépendances : aucune story externe, main 20a2e1b inclut l'installation existante.
Complexité : élevée, STANDARD. Une story intégrée car navigation, copie et tests
partagent le même contrat ; exécution séquentielle par un implementer.
Hors périmètre : runtime multi-agents propriétaire, installation tierce, application.

Verdict : PASS
