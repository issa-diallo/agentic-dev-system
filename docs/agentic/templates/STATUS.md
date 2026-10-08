# Agentic Status

## Project mode

`LIGHT | STANDARD | LARGE`

Selected mode: TODO

## Entrée

Selected entry: TODO (`PRODUCT` ou `EXISTING`)

Pour EXISTING : lier chaque ticket à son Research justifiant cette entrée.
Les statuts produit ci-dessous restent globaux : ne pas les marquer PASS pour
un ticket qui commence à Research. Leur absence de PASS ne bloque pas ce ticket
si les conditions d’EXISTING_PROJECT.md sont remplies.

## Product pipeline

| Phase | Status | Artifact | Blocker |
|---|---|---|---|
| PRD | TODO | `docs/product/PRD.md` | — |
| Stories | TODO | `docs/product/STORIES.md` | PRD |
| Story Review | TODO | `docs/product/STORY_REVIEW.md` | Stories |
| Architecture | TODO | `docs/product/ARCHITECTURE.md` | Story Review |
| Design System | TODO | `docs/product/DESIGN_SYSTEM.md` | Architecture |

Statuses: `TODO | IN_PROGRESS | PASS | BLOCKED`.

## Story pipeline

| Story | State | Research | Design | Plan | Worktree | Execute | Verify | Review | Goal | PR | CI | Blocker |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| — | BACKLOG | — | — | — | — | — | — | — | — | — | — | — |

Story states:

`BACKLOG -> RESEARCH -> DESIGN -> PLANNED -> IMPLEMENTING -> VERIFY -> REVIEW -> PR_OPEN -> CI -> READY_FOR_HUMAN -> DONE`

`BLOCKED` peut survenir à toute étape.
