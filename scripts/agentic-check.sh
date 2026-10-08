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

# Presence only: this does not validate phase gates or model behavior.
for resource in \
  AGENTS.md \
  COMMITS.md \
  docs/agentic/README.md \
  docs/agentic/METHOD.md \
  docs/agentic/WORKFLOW.md \
  docs/agentic/SCALING.md \
  docs/agentic/SAFETY.md \
  docs/agentic/EXISTING_PROJECT.md \
  docs/agentic/INSTALL.md \
  docs/agentic/LOCAL.md \
  docs/agentic/BOOTSTRAP.md \
  docs/agentic/CONTEXT.md \
  docs/agentic/MODELS.md \
  docs/agentic/OPTIONAL_TOOLS.md \
  docs/agentic/templates/ADR.md \
  docs/agentic/templates/ARCHITECTURE.md \
  docs/agentic/templates/DESIGN.md \
  docs/agentic/templates/DESIGN_SYSTEM.md \
  docs/agentic/templates/EXECUTE.md \
  docs/agentic/templates/GOAL.md \
  docs/agentic/templates/HANDOFF.md \
  docs/agentic/templates/PLAN.md \
  docs/agentic/templates/PRD.md \
  docs/agentic/templates/RESEARCH.md \
  docs/agentic/templates/REVIEW.md \
  docs/agentic/templates/SHIP.md \
  docs/agentic/templates/STATUS.md \
  docs/agentic/templates/STORIES.md \
  docs/agentic/templates/STORY.md \
  docs/agentic/templates/STORY_REVIEW.md \
  docs/agentic/templates/VERIFY.md \
  docs/agentic/templates/WORKTREE_ENVIRONMENT.md \
  docs/agentic/roles/IMPLEMENTER.md \
  docs/agentic/roles/ORCHESTRATOR.md \
  docs/agentic/roles/REVIEWER.md \
  docs/agentic/STATUS.md; do
  check_file "$resource"
done
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
