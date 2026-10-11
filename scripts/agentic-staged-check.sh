#!/usr/bin/env bash
# Read-only check: never stage, unstage, install a hook or alter Git configuration.
set -euo pipefail
fail() { echo "ERROR: $*" >&2; exit 1; }
case "${1:-}" in
  "") [ "$#" = 0 ] || fail "Usage: $0 [--amend] (from the project repository)" ;;
  --amend) [ "$#" = 1 ] || fail "Usage: $0 [--amend] (from the project repository)" ;;
  *) fail "Usage: $0 [--amend] (from the project repository)" ;;
esac
root="$(git rev-parse --show-toplevel)" || fail "A Git repository is required."
cd "$root"

# An amend recreates HEAD's whole change relative to its first parent.
# The root commit compares against the empty tree for this repository's object format.
diff_base=()
comparison_tree=HEAD
if [ "${1:-}" = --amend ]; then
  git rev-parse --verify HEAD >/dev/null || fail "Amend requires an existing commit."
  if ! comparison_tree="$(git rev-parse --verify HEAD^ 2>/dev/null)"; then
    comparison_tree="$(git hash-object -t tree --stdin < /dev/null)"
  fi
  diff_base=("$comparison_tree")
fi

personal_paths=()
manifest=.agentic-local/personal-paths.nul
if [ -e "$manifest" ] || [ -L "$manifest" ]; then
  [ -f "$manifest" ] && [ ! -L "$manifest" ] || fail "Invalid personal path manifest."
  path=
  while IFS= read -r -d '' path; do
    [ -n "$path" ] && [[ "$path" != /* && "$path" != ../* && "$path" != */../* && "$path" != */.. && "$path" != ./* && "$path" != */./* && "$path" != */. ]] ||
      fail "Personal paths must be exact repository-relative paths."
    personal_paths+=("$path")
  done < "$manifest"
  [ -z "$path" ] || fail "Personal path manifest must be NUL-terminated."
fi
is_personal() {
  local path="$1" selected
  case "$path" in
    .agentic-local|.agentic-local/*|*/.agentic-local|*/.agentic-local/*|docs/agentic/work|docs/agentic/work/*|docs/agentic/STATUS.md)
      return 0 ;;
  esac
  for selected in "${personal_paths[@]}"; do
    [ "$path" != "$selected" ] || return 0
  done
  return 1
}

# Fail if existing/future local files are exposed by changed team ignore rules.
# --no-index also checks exclusions for paths removed from the index in migration.
[ ! -L .agentic-local ] || fail "Refusing a symlinked local installation."
if [ -d .agentic-local ]; then
  paths_file="$(mktemp)"
  trap 'rm -f "$paths_file"' EXIT
  find .agentic-local -print0 > "$paths_file"
  printf '%s\0' .agentic-local/docs/agentic/work/probe/research.md >> "$paths_file"
  while IFS= read -r -d '' path; do
    git check-ignore --no-index -q -- "$path" || fail "Local exclusion is ineffective: $(printf '%q' "$path"). Restore local exclusions before committing."
  done < "$paths_file"
  rm -f "$paths_file"
  trap - EXIT
fi

# Rename/copy source AND destination are checked; pure index deletions are allowed.
# A temporary NUL stream preserves unusual names and propagates Git errors.
diff_file="$(mktemp)"
tree_file=
trap 'rm -f "$diff_file" "$tree_file"' EXIT
tree_file="$(mktemp)"
git diff --cached "${diff_base[@]}" --ignore-submodules=none --name-status -z --find-renames=50% --find-copies=100% --find-copies-harder > "$diff_file"
blocked=0
while IFS= read -r -d '' status; do
  IFS= read -r -d '' path || fail "Invalid staged diff."
  paths=("$path")
  case "$status" in
    D) continue ;;
    R*|C*) IFS= read -r -d '' destination || fail "Invalid staged rename/copy."
           # Empty blobs contain no private content: Git can infer a copy from any
           # empty note to a legitimate empty app file. Still inspect the target.
           copy_size=nonempty
           if [[ "$status" = C* ]] && is_personal "$path"; then
             # A gitlink points into another repository: its commit need not exist
             # here. Inspect tree metadata first and read size only for private blobs.
             git --literal-pathspecs ls-tree -z "$comparison_tree" -- "$path" > "$tree_file"
             IFS= read -r -d '' entry < "$tree_file" || fail "Missing copy source."
             metadata="${entry%%$'\t'*}"
             read -r mode object_type object_id <<< "$metadata"
             if [ "$object_type" = blob ]; then
               copy_size="$(git cat-file -s "$object_id")"
             fi
           fi
           if [ "$copy_size" = 0 ]; then
             paths=("$destination")
           else
             paths+=("$destination")
           fi ;;
  esac
  for path in "${paths[@]}"; do
    if is_personal "$path"; then
      printf 'BLOCKED: personal Agentic path staged: %q\n' "$path" >&2
      blocked=1
    fi
  done
done < "$diff_file"
[ "$blocked" = 0 ] || fail "Commit refused. Unstage personal files; preserve their physical contents."
echo "Agentic staged check passed."
