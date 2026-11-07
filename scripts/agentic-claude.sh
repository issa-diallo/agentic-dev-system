#!/usr/bin/env bash
# Ephemeral subagent definitions only (--agents). Keeps settings, permissions and CLAUDE.md intact.
set -euo pipefail
METHOD_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
command -v claude >/dev/null || { echo 'ERROR: claude is required.' >&2; exit 1; }
command -v python3 >/dev/null || { echo 'ERROR: python3 is required.' >&2; exit 1; }
agents="$(python3 "$METHOD_ROOT/scripts/agentic-run.py" claude-agents)" || exit 1
if [ "${1:-}" = run ]; then
  [ "$#" -ge 2 ] && [ -n "$2" ] || { echo 'Usage: agentic-claude.sh run <mission> [Claude options]' >&2; exit 2; }
  mission="$2"
  shift 2
  activation="Read the repository and team rules first. Then read the Agentic method at $METHOD_ROOT/docs/agentic/LOCAL.md and $METHOD_ROOT/docs/agentic/README.md. Use PREPARE -> BUILD -> SHIP; reuse validated decisions. Require PR_SPLIT before nontrivial BUILD. To delegate an implementation to a cheaper model use python3 $METHOD_ROOT/scripts/agentic-run.py (see $METHOD_ROOT/docs/agentic/DELEGATION.md); its gates are mechanical and never replace the independent review. Subagent profiles are definitions, not proof of launch: keep observed receipts. Preserve team rules and existing permissions."
  exec claude --agents "$agents" --append-system-prompt "$activation" "$@" "$mission"
fi
exec claude --agents "$agents" "$@"
