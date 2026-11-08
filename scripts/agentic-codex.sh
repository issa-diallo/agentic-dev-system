#!/usr/bin/env bash
# Native agents are installed in the project's .codex/agents directory.
set -euo pipefail
METHOD_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
command -v codex >/dev/null || { echo 'ERROR: codex is required.' >&2; exit 1; }
if [ "${1:-}" = run ]; then
  [ "$#" -ge 2 ] && [ -n "$2" ] || { echo 'Usage: agentic-codex.sh run <mission> [Codex options]' >&2; exit 2; }
  mission="$2"
  shift 2
  activation="Read the repository and team rules first. Then read the Agentic method at $METHOD_ROOT/docs/agentic/LOCAL.md and $METHOD_ROOT/docs/agentic/README.md. Use PREPARE -> BUILD -> SHIP; reuse validated decisions, and use $METHOD_ROOT/docs/agentic/templates/PREPARE.md only for needed sections. Route skills with $METHOD_ROOT/scripts/agentic-skills.py using the explicit root $METHOD_ROOT/skills plus other roots already known and authorized by the host. Load only selected skills; reading is not application. Require PR_SPLIT before nontrivial BUILD. Native delegation and independent review need observed runtime receipts; profiles alone are not active agents. Preserve team rules and existing permissions.

User mission:
"
  set -- "$@" "$activation$mission"
fi
exec codex "$@"
