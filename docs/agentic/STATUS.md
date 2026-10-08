# Agentic Status

## Project mode

`LIGHT | STANDARD | LARGE`

Selected mode: STANDARD

## Entrée

Selected entry: PRODUCT (`PRODUCT` ou `EXISTING`)

Pour EXISTING : lier chaque ticket à son Research justifiant cette entrée.
Les statuts produit ci-dessous restent globaux : ne pas les marquer PASS pour
un ticket qui commence à Research. Leur absence de PASS ne bloque pas ce ticket
si les conditions d’EXISTING_PROJECT.md sont remplies.

## Product pipeline

| Phase | Status | Artifact | Blocker |
|---|---|---|---|
| PRD | PASS | `docs/product/PRD.md` | — |
| Stories | PASS | `docs/product/STORIES.md` | — |
| Story Review | PASS | `docs/product/STORY_REVIEW.md` | — |
| Architecture | PASS | `docs/product/ARCHITECTURE.md` | — |
| Design System | PASS | `docs/product/DESIGN_SYSTEM.md` | — |

Statuses: `TODO | IN_PROGRESS | PASS | BLOCKED`.

## Story pipeline

| Story | State | Research | Design | Plan | Worktree | Execute | Verify | Review | Goal | PR | CI | Blocker |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| #6 | READY_FOR_HUMAN | PASS | PASS | PASS | PASS | PASS | PASS | PASS | SATISFIED | [#7](https://github.com/issa-diallo/agentic-dev-system/pull/7) | PASS | aucun |

Story states:

`BACKLOG -> RESEARCH -> DESIGN -> PLANNED -> IMPLEMENTING -> VERIFY -> REVIEW -> PR_OPEN -> CI -> READY_FOR_HUMAN -> DONE`

`BLOCKED` peut survenir à toute étape.
