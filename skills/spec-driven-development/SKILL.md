---
name: spec-driven-development
description: Specification before code for new, vague or multi-capability work, reusing approved framing and resolving blocking decisions before planning.
---

Use in PREPARE when the request is new, ambiguous or spans several independent capabilities. Reuse approved framing, PRD/TRD and decisions per [SCALING](../../docs/agentic/SCALING.md); never create a parallel spec format. Record assumptions and resolve blocking ambiguities from available sources; ask the human only for an indispensable unresolved decision or an explicitly required authorization. Cover objective, commands, structure, code style, tests, boundaries (always / ask first / never) and specific, testable success criteria. Map independent capabilities, stable ids, dependencies and build order through [PR_SPLIT](../../docs/agentic/PULL_REQUESTS.md). The orchestrator validates the split without systematic human approval; required independent reviews remain mandatory. Report PASS or BLOCKED with evidence; on PASS, continue planning without ending the turn just to request approval. Preparation stays local under `.agentic-local/docs/agentic/work/` and is never committed ([COMMITS](../../COMMITS.md)).

Adapted from addyosmani/agent-skills (MIT, Copyright (c) 2025 Addy Osmani, commit 301b02b).
