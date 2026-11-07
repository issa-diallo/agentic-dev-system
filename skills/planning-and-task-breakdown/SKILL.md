---
name: planning-and-task-breakdown
description: Break an approved spec into ordered, vertically sliced tasks with acceptance criteria, verification and checkpoints before nontrivial BUILD.
---

Use after the spec is approved, feeding IMPLEMENTATION_PLAN and PR_SPLIT ([PULL_REQUESTS](../../docs/agentic/PULL_REQUESTS.md)) without replacing them. Read-only: write no code while planning. Map the dependency graph, build foundations first and risky work early. Slice vertically: one complete working path per task, never all schema, then all API, then all UI. Each task has a title without "and", at most three testable acceptance criteria, one verification step (test, build or manual check), dependencies, files likely touched and a size. Target XS to M (1 to 5 files); split L, refuse XL. Add a checkpoint every two or three tasks (tests pass, build clean, flow works). Mark what can run in parallel, what must stay sequential and which shared contracts to define first. Plans stay local under docs/agentic/work/ and are never committed ([COMMITS](../../COMMITS.md)); never overwrite a plan that still has unchecked tasks, stop and ask.

Adapted from addyosmani/agent-skills (MIT, Copyright (c) 2025 Addy Osmani, commit 301b02b).
