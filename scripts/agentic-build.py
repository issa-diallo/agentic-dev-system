#!/usr/bin/env python3
"""Validate a BUILD delegation before dispatch; not a filesystem sandbox.

The caller must dispatch immediately and retain the returned plan hash. Every
new dispatch must call prepare again. completed contains dependency IDs whose
completion the orchestrator has verified; this gate does not authenticate agents,
execute tests, launch agents, reserve resources or prevent arbitrary shell edits.
"""
import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

_SPEC = importlib.util.spec_from_file_location(
    "agentic_pr_check", Path(__file__).with_name("agentic-pr-check.py"))
_CHECK = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_CHECK)
Blocked = _CHECK.Blocked


def git(repo, *args):
    return _CHECK.git(str(repo), *args)


def common_dir(repo):
    value = git(repo, "rev-parse", "--git-common-dir").decode().strip()
    return (Path(repo) / value).resolve()


def dirty_paths(repo):
    entries = git(repo, "status", "--porcelain=v1", "-z", "--untracked-files=all").split(b"\0")
    paths, index = set(), 0
    while index < len(entries) - 1:
        entry = entries[index]
        paths.add(entry[3:].decode("utf-8", "surrogateescape"))
        if b"R" in entry[:2] or b"C" in entry[:2]:
            index += 1
            paths.add(entries[index].decode("utf-8", "surrogateescape"))
        index += 1
    return paths


def prepare(manifest_path, repo, pr_id, completed=()):
    """Return a freshly validated delegation; dependency IDs are caller evidence.

    V1 manifests are supported unchanged. Pending/stacked dependencies wait for
    verified completion: contract stability alone never implies completion.
    """
    root = Path(git(repo, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    plan = _CHECK.load_json(manifest_path)
    units, _ = _CHECK.check_plan(plan, root)
    _CHECK.require(pr_id in units, "unknown PR")
    pr = units[pr_id]
    _CHECK.require(not isinstance(completed, (str, bytes)), "completed must contain dependency IDs")
    done = set(completed)
    _CHECK.require(all(isinstance(item, str) and item in units for item in done),
                   "unknown completed dependency")
    pending, required = list(pr["depends_on"]), set()
    while pending:
        dependency = pending.pop()
        if dependency not in required:
            required.add(dependency)
            pending.extend(units[dependency]["depends_on"])
    _CHECK.require(required <= done, "dependencies not completed: " + ", ".join(sorted(required - done)))
    tree = (root / pr["worktree"]).resolve()
    _CHECK.require(tree.is_dir(), "assigned worktree does not exist")
    actual = Path(git(tree, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    _CHECK.require(actual == tree and common_dir(tree) == common_dir(root),
                   "assigned worktree is not linked to this repository")
    branch = git(tree, "symbolic-ref", "--quiet", "--short", "HEAD").decode().strip()
    _CHECK.require(branch not in ("main", "master"), "BUILD cannot write main/master")
    _CHECK.require(branch == pr["branch"], "assigned worktree has wrong branch")
    outside = dirty_paths(tree) - set(pr["files"])
    _CHECK.require(not outside, "dirty paths outside scope: " + ", ".join(sorted(outside)))
    return {"pr": pr_id, "plan_sha256": _CHECK.plan_hash(plan),
            "objective": pr["reason"], "acceptance": pr["acceptance"],
            "files": pr["files"], "tests": pr["tests"],
            "dependencies": pr["depends_on"], "branch": branch,
            "worktree": str(tree), "implementer": pr["implementer"],
            "prohibitions": ["Write only declared files in the assigned worktree",
                             "Do not change scope or stack without revalidation",
                             "Do not merge, publish or claim unexecuted tests",
                             "One writer per worktree; reserve shared resources before dispatch"],
            "deliverable": "Scoped diff, executed validation evidence and handoff"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--pr", required=True)
    parser.add_argument("--completed", action="append", default=[])
    args = parser.parse_args()
    result = {"gate": "BUILD_READY", "verdict": "BLOCKED"}
    try:
        result["delegation"] = prepare(args.manifest, args.repo, args.pr, args.completed)
        result.update(verdict="PASS", reason="Current plan and Git assignment validated")
    except (Blocked, OSError, ValueError, TypeError, KeyError) as error:
        result["reason"] = str(error)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
