---
name: spec-driven-development
description: Specification before code for new, vague or multi-capability work: surface assumptions, write a testable spec, stop for human approval before planning.
---

Use in PREPARE when the request is new, ambiguous or spans several independent capabilities. Reuse PRD/TRD per [SCALING](../../docs/agentic/SCALING.md); never create a parallel spec format. List assumptions first and ask the human to correct them; never fill ambiguity silently. Cover objective, commands, structure, code style, tests, boundaries (always / ask first / never) and success criteria that are specific and testable ("faster" becomes a measured target). If one request bundles independently testable capabilities, propose a short capability map (stable ids, one-way dependencies, build order) for approval before any module spec. Report PASS or BLOCKED with open questions, then stop the turn; plan only after human approval in a later turn. Specs, plans and briefs stay local under docs/agentic/work/ and are never committed ([COMMITS](../../COMMITS.md)).

Adapted from addyosmani/agent-skills (MIT, Copyright (c) 2025 Addy Osmani, commit 301b02b).
