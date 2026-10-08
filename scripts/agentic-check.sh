#!/usr/bin/env bash
set -euo pipefail

case "${1:-}" in
  "") entry=PRODUCT ;;
  --existing) entry=EXISTING ;;
  *) echo "Usage: $0 [--existing]" >&2; exit 2 ;;
esac
if [ "$#" -gt 1 ]; then
  echo "Usage: $0 [--existing]" >&2
  exit 2
fi

fail=0

check_file() {
  if [ ! -f "$1" ]; then
    echo "MISSING: $1"
    fail=1
  else
    echo "OK: $1"
  fi
}

check_file "AGENTS.md"
check_file "COMMITS.md"
check_file "docs/agentic/METHOD.md"
check_file "docs/agentic/WORKFLOW.md"
if [ "$entry" = "EXISTING" ]; then
  check_file "docs/agentic/EXISTING_PROJECT.md"
else
  check_file "docs/product/PRD.md"
  check_file "docs/product/STORIES.md"
  check_file "docs/product/STORY_REVIEW.md"
  check_file "docs/product/ARCHITECTURE.md"
  check_file "docs/product/DESIGN_SYSTEM.md"
fi

if [ "$fail" -ne 0 ]; then
  echo "Agentic method check failed."
  exit 1
fi

echo "Agentic presence check passed ($entry). Content and phase gates require review."
