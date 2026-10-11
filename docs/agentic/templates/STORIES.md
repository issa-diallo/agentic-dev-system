# Stories — <Produit>

## Status

`STORIES: DRAFT | PASS | BLOCKED`

## Convention

Chaque story doit être fonctionnelle, testable et aussi indépendante que possible.

## Story S01 — <titre>

**En tant que** …
**Je veux** …
**Afin de** …

### Critères d'acceptation
- [ ] …
- [ ] …

### Dépendances
- aucune / Sxx

### Hors périmètre
- …

### Complexité
S / M / L / XL

---

## Dependency map

```text
S01
 ├─> S02
 └─> S03
```

## Stories Gate

- [ ] chaque capacité PRD est couverte
- [ ] critères d'acceptation présents
- [ ] dépendances explicites
- [ ] pas de story manifestement trop large
- [ ] pas de story purement technique déguisée

Verdict : PASS / BLOCKED

## Découpage en unités de PR

La story contient le besoin ; elle ne fixe pas une PR unique. Identifier les
capacités métier autonomes et leurs AC. Research/Design communs peuvent être
hérités par plusieurs unités ; garder fichiers, tests, contrats et Plan par PR.
Après Plan, remplir `docs/agentic/templates/PR_SPLIT.md` : capacité → PR → AC/tests/fichiers,
DAG, ordre de fusion, vagues, stack, branche/worktree et implementer.
Une capacité séparable par PR ; code, tests et migrations indispensables ensemble.
En LIGHT, une entrée compacte dans Plan suffit. PR_SPLIT PASS avant Execute.
