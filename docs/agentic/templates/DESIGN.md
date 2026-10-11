# Design — <story> <titre>

## Status

`DESIGN: DRAFT | PASS | BLOCKED`

## Inputs

- Story :
- Research :
- Design System :
- Architecture :

## User flow

```text
<flow>
```

## Screens / interfaces

### Screen / Interface 1
- purpose :
- fields/data :
- actions :
- validation :

## States

- loading :
- empty :
- error :
- success :
- unauthorized :
- offline/retry si pertinent :

## Responsive / accessibility

- …

## API or domain interaction

- …

## Edge cases

- …

## Design Gate

- [ ] critères d'acceptation représentés
- [ ] états importants couverts
- [ ] design system respecté
- [ ] architecture respectée
- [ ] aucune ambiguïté bloquante

Verdict : PASS / BLOCKED

## Découpage en unités de PR

La story contient le besoin ; elle ne fixe pas une PR unique. Identifier les
capacités métier autonomes et leurs AC. Research/Design communs peuvent être
hérités par plusieurs unités ; garder fichiers, tests, contrats et Plan par PR.
Après Plan, remplir [PR_SPLIT](PR_SPLIT.md) : capacité → PR → AC/tests/fichiers,
DAG, ordre de fusion, vagues, stack, branche/worktree et implementer.
Une capacité séparable par PR ; code, tests et migrations indispensables ensemble.
En LIGHT, une entrée compacte dans Plan suffit. PR_SPLIT PASS avant Execute.
