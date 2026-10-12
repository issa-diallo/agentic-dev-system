---
name: parallel-execution-worktrees
description: Parallel execution and Git worktrees for independent missions requiring isolated writers and shared-resource ownership.
---

Before nontrivial BUILD require PR_SPLIT PASS. Read [PULL_REQUESTS](../../docs/agentic/PULL_REQUESTS.md) and [WORKTREE_ENVIRONMENT](../../docs/agentic/templates/WORKTREE_ENVIRONMENT.md). Reserve exact files plus logical shared resources through scripts/agentic-workspace.py. One writer per worktree; no auto-cleanup of unintegrated work. Scheduler plans dispatch; the host must actually launch agents and retain receipts. Fall back honestly when delegation is unavailable.
