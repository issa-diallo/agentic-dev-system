#!/usr/bin/env bash
# Ephemeral agent overrides only. Keep account, user config and permissions intact.
set -euo pipefail
METHOD_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
command -v codex >/dev/null || { echo 'ERROR: codex is required.' >&2; exit 1; }
command -v python3 >/dev/null || { echo 'ERROR: python3 is required.' >&2; exit 1; }
overrides=()
for role in explorer implementer reviewer; do
  profile="$METHOD_ROOT/codex/agents/$role.toml"
  [ -f "$profile" ] && [ ! -L "$profile" ] || { echo "ERROR: Missing native profile: $role" >&2; exit 1; }
  quoted="$(python3 -c 'import json,sys; print(json.dumps(sys.argv[1], ensure_ascii=False))' "$profile")"
  overrides+=(-c "agents.agentic_$role.config_file=$quoted")
done
if [ "${1:-}" = run ]; then
  [ "$#" -ge 2 ] && [ -n "$2" ] || { echo 'Usage: agentic-codex.sh run <mission> [Codex options]' >&2; exit 2; }
  mission="$2"
  shift 2
  activation="Read the repository and team rules first. Then read the Agentic method at $METHOD_ROOT/docs/agentic/LOCAL.md and $METHOD_ROOT/docs/agentic/README.md. Use PREPARE -> BUILD -> SHIP; reuse validated decisions, and use $METHOD_ROOT/docs/agentic/templates/PREPARE.md only for needed sections. Route skills with $METHOD_ROOT/scripts/agentic-skills.py using the explicit root $METHOD_ROOT/skills plus other roots already known and authorized by the host. Load only selected skills; reading is not application. Require PR_SPLIT before nontrivial BUILD. Native delegation and independent review need observed runtime receipts; profiles alone are not active agents. Preserve team rules and existing permissions.

User mission:
"
  set -- "$@" "$activation$mission"
fi
exec codex "${overrides[@]}" "$@"
