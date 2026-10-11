#!/usr/bin/env bash
# Commit only the already staged index after the mandatory personal-file check.
set -euo pipefail
fail() { echo "ERROR: $*" >&2; exit 1; }
args=("$@")
check_args=()
# Restrict options so git commit cannot add paths AFTER the staged check (-a, -i, -o...).
while [ "$#" -gt 0 ]; do
  case "$1" in
    -m|--message|-F|--file)
      [ "$#" -ge 2 ] || fail "Missing value for $1"
      shift 2 ;;
    --amend) check_args=(--amend); shift ;;
    --message=*|--file=*|--no-edit|--allow-empty|--signoff|-s) shift ;;
    *) fail "Unsupported commit option/path: $1. Stage explicitly, then use -m or -F (optional --amend/--no-edit/--signoff/--allow-empty)." ;;
  esac
done
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
bash "$SCRIPT_DIR/agentic-staged-check.sh" "${check_args[@]}"
exec git commit "${args[@]}"
