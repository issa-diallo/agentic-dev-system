#!/usr/bin/env bash
set -euo pipefail

TARGET="${1:-.}"
FORCE="${FORCE:-0}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

fail() {
  echo "ERROR: $*" >&2
  exit 1
}

[ -d "$TARGET" ] || fail "Target directory does not exist: $TARGET"
[ -f "$SCRIPT_DIR/AGENTS.md" ] || fail "AGENTS.md not found next to installer."
[ -d "$SCRIPT_DIR/docs/agentic" ] || fail "docs/agentic not found next to installer."

mkdir -p "$TARGET/docs"

if [ -e "$TARGET/AGENTS.md" ] && [ "$FORCE" != "1" ]; then
  fail "AGENTS.md already exists in target. Re-run with FORCE=1 only if you intentionally want to replace it."
fi

if [ -e "$TARGET/docs/agentic" ] && [ "$FORCE" != "1" ]; then
  fail "docs/agentic already exists in target. Re-run with FORCE=1 only if you intentionally want to replace it."
fi

if [ "$FORCE" = "1" ]; then
  rm -rf "$TARGET/docs/agentic"
fi

cp "$SCRIPT_DIR/AGENTS.md" "$TARGET/AGENTS.md"
cp -R "$SCRIPT_DIR/docs/agentic" "$TARGET/docs/agentic"

mkdir -p "$TARGET/docs/product"
mkdir -p "$TARGET/docs/agentic/work"

copy_if_missing() {
  local src="$1"
  local dest="$2"
  if [ ! -e "$dest" ]; then
    cp "$src" "$dest"
  fi
}

copy_if_missing "$SCRIPT_DIR/docs/agentic/templates/PRD.md" "$TARGET/docs/product/PRD.md"
copy_if_missing "$SCRIPT_DIR/docs/agentic/templates/STORIES.md" "$TARGET/docs/product/STORIES.md"
copy_if_missing "$SCRIPT_DIR/docs/agentic/templates/STORY_REVIEW.md" "$TARGET/docs/product/STORY_REVIEW.md"
copy_if_missing "$SCRIPT_DIR/docs/agentic/templates/ARCHITECTURE.md" "$TARGET/docs/product/ARCHITECTURE.md"
copy_if_missing "$SCRIPT_DIR/docs/agentic/templates/DESIGN_SYSTEM.md" "$TARGET/docs/product/DESIGN_SYSTEM.md"

echo
echo "Agentic Development System installed in: $TARGET"
echo
echo "Pipeline:"
echo "PRD -> Stories -> Story Review -> Architecture -> Design System -> Research -> Design -> Plan -> Execute -> Review -> Ship"
echo
echo "Next:"
echo "1. Open the target project."
echo "2. Ask the agent to read AGENTS.md and docs/agentic/METHOD.md."
echo "3. Tell it to start from the first phase not marked PASS."
