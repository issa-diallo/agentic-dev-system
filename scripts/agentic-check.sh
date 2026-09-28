#!/usr/bin/env bash
set -euo pipefail

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
check_file "docs/product/PRD.md"
check_file "docs/product/STORIES.md"
check_file "docs/product/STORY_REVIEW.md"
check_file "docs/product/ARCHITECTURE.md"
check_file "docs/product/DESIGN_SYSTEM.md"

if [ "$fail" -ne 0 ]; then
  echo "Agentic method check failed."
  exit 1
fi

echo "Agentic method check passed."
