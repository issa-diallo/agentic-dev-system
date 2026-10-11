# Story — <ticket> <titre>

## User story

En tant que <acteur>, je veux <capacité>, afin de <valeur>.

## Contexte

<Pourquoi cette story existe.>

## Critères d'acceptation

- [ ] AC1 —
- [ ] AC2 —
- [ ] AC3 —

## Hors périmètre

- …

## Dépendances

- …

## Risques connus

- …

## Données / sécurité

- Tenant concerné :
- Autorisations :
- Données sensibles :
- Validation humaine requise :

## Définition de Done

- [ ] critères d'acceptation satisfaits
- [ ] tests pertinents ajoutés
- [ ] review indépendante passée
- [ ] CI verte
- [ ] PR validée humainement

## Découpage en unités de PR

La story contient le besoin ; elle ne fixe pas une PR unique. Identifier les
capacités métier autonomes et leurs AC. Research/Design communs peuvent être
hérités par plusieurs unités ; garder fichiers, tests, contrats et Plan par PR.
Après Plan, remplir [PR_SPLIT](PR_SPLIT.md) : capacité → PR → AC/tests/fichiers,
DAG, ordre de fusion, vagues, stack, branche/worktree et implementer.
Une capacité séparable par PR ; code, tests et migrations indispensables ensemble.
En LIGHT, une entrée compacte dans Plan suffit. PR_SPLIT PASS avant Execute.
