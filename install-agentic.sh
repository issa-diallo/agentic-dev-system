#!/usr/bin/env bash
set -euo pipefail

fail() { echo "ERROR: $*" >&2; exit 1; }
usage() { echo "Usage: $0 [--existing | --local] [target-directory]"; }
MODE=PRODUCT
TARGET=.
target_set=0
for arg in "$@"; do
  case "$arg" in
    --local) MODE=LOCAL ;;
    --existing) [ "$MODE" = LOCAL ] || MODE=EXISTING ;;
    --help|-h) usage; exit 0 ;;
    -*) usage >&2; fail "Unknown option: $arg" ;;
    *) [ "$target_set" = 0 ] || fail "Only one target is allowed."
       TARGET="$arg"; target_set=1 ;;
  esac
done
[ "${FORCE:-0}" = 0 ] || fail "FORCE is no longer supported. Compare and back up existing files before a manual update."
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
[ -d "$TARGET" ] || fail "Target directory does not exist: $TARGET"
TARGET="$(cd "$TARGET" && pwd -P)"
[ "$TARGET" != "$SCRIPT_DIR" ] || fail "Cannot install into the source repository."
# Validate every required portable resource before any target write.
for source in \
  AGENTS.md \
  COMMITS.md \
  scripts/agentic-check.sh \
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
  docs/agentic/roles/REVIEWER.md; do
  [ -f "$SCRIPT_DIR/$source" ] || fail "Missing source: $source"
done

DEST="$TARGET"
if [ "$MODE" = LOCAL ]; then
  root="$(git -C "$TARGET" rev-parse --show-toplevel)" || fail "Local mode requires a Git repository."
  [ "$TARGET" = "$(cd "$root" && pwd -P)" ] || fail "Use the Git repository root as target."
  DEST="$TARGET/.agentic-local"
  [ ! -e "$DEST" ] && [ ! -L "$DEST" ] || fail ".agentic-local already exists; no files changed."
  [ -z "$(git -C "$TARGET" ls-files -- .agentic-local)" ] || fail ".agentic-local contains tracked paths."
  EXCLUDE="$(git -C "$TARGET" rev-parse --path-format=absolute --git-path info/exclude)"
  [ ! -L "$EXCLUDE" ] && [ ! -L "$(dirname "$EXCLUDE")" ] || fail "Refusing a symlinked Git exclude path."
else
  # Preflight all destinations before creating directories or copying files.
  for dir in docs scripts hooks .github .github/ISSUE_TEMPLATE docs/product docs/adr; do
    [ ! -L "$TARGET/$dir" ] || fail "Refusing symlink: $dir"
    [ ! -e "$TARGET/$dir" ] || [ -d "$TARGET/$dir" ] || fail "Not a directory: $dir"
  done
  for protected in AGENTS.md COMMITS.md docs/agentic; do
    [ ! -e "$TARGET/$protected" ] && [ ! -L "$TARGET/$protected" ] || fail "$protected already exists. Use --local to preserve team files."
  done
fi

copy_if_missing() {
  local src="$1" dest="$2"
  if [ ! -e "$dest" ] && [ ! -L "$dest" ]; then
    mkdir -p "$(dirname "$dest")"
    cp "$src" "$dest"
  fi
}

if [ "$MODE" = LOCAL ]; then
  mkdir -p "$(dirname "$EXCLUDE")"
  exclude_backup="$(mktemp)"
  exclude_existed=0
  if [ -e "$EXCLUDE" ]; then
    cp "$EXCLUDE" "$exclude_backup"
    exclude_existed=1
  fi
  # Leading newline preserves an existing last line without a newline.
  if ! grep -Fxq '/.agentic-local/' "$EXCLUDE" 2>/dev/null; then
    printf '\n# Personal agentic method\n/.agentic-local/\n' >> "$EXCLUDE"
  fi
  # Team .gitignore rules outrank info/exclude. Check every planned file,
  # including a probe for future story notes, before installing anything.
  ignored=1
  paths=(.agentic-local/AGENTS.md .agentic-local/COMMITS.md
    .agentic-local/scripts/agentic-check.sh
    .agentic-local/docs/agentic/STATUS.md
    .agentic-local/docs/agentic/work/probe/research.md)
  while IFS= read -r -d '' source; do
    paths+=(".agentic-local/${source#"$SCRIPT_DIR/"}")
  done < <(find "$SCRIPT_DIR/docs/agentic" -path "$SCRIPT_DIR/docs/agentic/work" -prune -o -type f -print0)
  for path in "${paths[@]}"; do
    if ! git -C "$TARGET" check-ignore --no-index -q -- "$path"; then
      ignored=0
      break
    fi
  done
  if [ "$ignored" = 0 ]; then
    if [ "$exclude_existed" = 1 ]; then
      cp "$exclude_backup" "$EXCLUDE"
    else
      rm -f "$EXCLUDE"
    fi
    rm -f "$exclude_backup"
    fail "Team ignore rules expose local files; no installation performed. Use an external personal directory."
  fi
  rm -f "$exclude_backup"
fi
mkdir -p "$DEST/docs/agentic"
cp "$SCRIPT_DIR/AGENTS.md" "$DEST/AGENTS.md"
cp "$SCRIPT_DIR/COMMITS.md" "$DEST/COMMITS.md"
# Never distribute source-project story evidence or local status.
for entry in "$SCRIPT_DIR/docs/agentic/"*; do
  case "$(basename "$entry")" in work|STATUS.md) continue ;; esac
  cp -R "$entry" "$DEST/docs/agentic/"
done
cp "$SCRIPT_DIR/docs/agentic/templates/STATUS.md" "$DEST/docs/agentic/STATUS.md"
mkdir -p "$DEST/docs/agentic/work"
copy_if_missing "$SCRIPT_DIR/scripts/agentic-check.sh" "$DEST/scripts/agentic-check.sh"
if [ "$MODE" = PRODUCT ]; then
  for name in PRD STORIES STORY_REVIEW ARCHITECTURE DESIGN_SYSTEM; do
    copy_if_missing "$SCRIPT_DIR/docs/agentic/templates/$name.md" "$DEST/docs/product/$name.md"
  done
  mkdir -p "$DEST/docs/adr"
fi
if [ "$MODE" != LOCAL ]; then
  for file in hooks/README.md .github/ISSUE_TEMPLATE/story.yml .github/pull_request_template.md; do
    [ ! -f "$SCRIPT_DIR/$file" ] || copy_if_missing "$SCRIPT_DIR/$file" "$DEST/$file"
  done
fi

echo "Installed $MODE in: $DEST"
if [ "$MODE" = LOCAL ]; then
  echo "Team files are unchanged. Nothing is automatically activated."
  echo "Prompt: Read the repository rules first, then .agentic-local/docs/agentic/LOCAL.md for ticket <id>."
  echo "Check: (cd .agentic-local && bash scripts/agentic-check.sh --existing)"
else
  echo "Read AGENTS.md and docs/agentic/README.md."
  echo "PRODUCT starts with product phases; EXISTING starts with a scoped ticket and Research."
  echo "Check: bash scripts/agentic-check.sh $([ "$MODE" = PRODUCT ] || printf '%s' '--existing')"
fi
echo "Choose LIGHT, STANDARD or LARGE by risk. Templates and presence checks do not imply gate PASS."
