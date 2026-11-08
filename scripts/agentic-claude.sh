#!/usr/bin/env bash
# Native agents are installed in the project's .claude/agents directory.
set -euo pipefail
METHOD_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
command -v claude >/dev/null || { echo 'ERROR: claude is required.' >&2; exit 1; }
if [ "${1:-}" = run ]; then
  [ "$#" -ge 2 ] && [ -n "$2" ] || { echo 'Usage: agentic-claude.sh run <mission> [Claude options]' >&2; exit 2; }
  mission="$2"
  shift 2
  activation="Read the repository and team rules first. Then read the Agentic method at $METHOD_ROOT/docs/agentic/LOCAL.md and $METHOD_ROOT/docs/agentic/README.md. Use PREPARE -> BUILD -> SHIP; reuse validated decisions. Require PR_SPLIT before nontrivial BUILD. To delegate an implementation to a cheaper model use python3 $METHOD_ROOT/scripts/agentic-run.py (see $METHOD_ROOT/docs/agentic/DELEGATION.md); its gates are mechanical and never replace the independent review. Subagent profiles are definitions, not proof of launch: keep observed receipts. Preserve team rules and existing permissions."
  exec claude --append-system-prompt "$activation" "$@" "$mission"
fi
exec claude "$@"
