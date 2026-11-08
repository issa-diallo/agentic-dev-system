---
name: planning-and-task-breakdown
description: Turn clear or previously approved PREPARE inputs into ordered, vertically sliced tasks with acceptance criteria, verification and checkpoints before nontrivial BUILD.
---

Use after PREPARE inputs are sufficiently clear, reusing approved framing and feeding IMPLEMENTATION_PLAN and PR_SPLIT ([PULL_REQUESTS](../../docs/agentic/PULL_REQUESTS.md)) without replacing them. Write no application code or tests while planning. Map the dependency graph, build foundations first and risky work early. Slice vertically: one complete working path per task, never all schema, then all API, then all UI. Each task has a precise title, testable acceptance criteria, verification commands/evidence, dependencies, exact files and a size. Follow PULL_REQUESTS for sizing and justified exceptions. Mark independent work, sequential work and shared contracts to stabilize first. The orchestrator validates PR_SPLIT without systematic human approval, preserving required independent reviews. On PASS, hand the artifacts to the next authorized phase without a manual pause. Plans stay local under `.agentic-local/docs/agentic/work/` and are never committed ([COMMITS](../../COMMITS.md)). Reconcile an existing plan with Git, remaining tasks and ownership; preserve completed work and update only the affected scope. Ask only when an indispensable decision or authorization is missing.

Adapted from addyosmani/agent-skills (MIT, Copyright (c) 2025 Addy Osmani, commit 301b02b).
