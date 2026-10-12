# Execute — <story>

## Preconditions

- [ ] PREPARE PASS, six rubriques/sources réutilisées accessibles
- [ ] PR_SPLIT PASS pour BUILD non trivial
- [ ] architecture/ADR compatibles
- [ ] branche/worktree corrects et owner unique pour PR non triviale
- [ ] ressources réservées sans collision, environnement prêt selon le risque
- [ ] dépendances acceptées avec preuves fraîches et contrats compatibles
- [ ] lancement observé et autorisation de commencer, ou fallback explicite
- [ ] aucun blocker

Les artefacts Research/Design/Plan V1 restent des sources legacy facultatives ;
aucun PASS distinct supplémentaire requis. Une attribution n'est pas un lancement.

## Implementation checklist

- [ ] suivre le plan
- [ ] rester dans le scope
- [ ] écrire/adapter les tests
- [ ] traiter erreurs et edge cases
- [ ] respecter architecture
- [ ] respecter design system
- [ ] respecter sécurité/authz/tenant
- [ ] ne pas modifier silencieusement la stack

## Commands executed

| Command | Result |
|---|---|
| … | PASS/FAIL |

## Deviations from plan

Toute déviation doit être justifiée.

- …

## Handoff

Préparer `handoff.md` pour Verify et Review.

## Execute Gate

- [ ] implémentation complète
- [ ] tests locaux pertinents exécutés
- [ ] diff inspecté
- [ ] handoff prêt

Verdict : PASS / BLOCKED
