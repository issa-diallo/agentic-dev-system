#!/usr/bin/env python3
"""Check declared PR boundaries and Git evidence; never classify business intent."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys


class Blocked(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Blocked(message)


def nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def strings(value, label, empty=False):
    require(isinstance(value, list) and (empty or value), f"{label}: list required")
    require(all(nonempty(item) for item in value), f"{label}: nonempty strings required")
    require(len(value) == len(set(value)), f"{label}: duplicate entries")
    return value


def load_json(path):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(Path(path).read_text(), object_pairs_hook=unique)


def plan_hash(plan):
    encoded = json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def justified(value, label, implementer=None):
    require(isinstance(value, dict), f"{label}: justification required")
    for key in ("constraint", "evidence", "split_risk"):
        require(nonempty(value.get(key)), f"{label}: {key} required")
    if implementer is not None:
        require(nonempty(value.get("reviewer")) and value["reviewer"] != implementer,
                f"{label}: independent reviewer required")


def check_plan(plan, repo):
    require(isinstance(plan, dict) and plan.get("version") == 1, "plan version must be 1")
    require(nonempty(plan.get("story")), "story required")
    capabilities = strings(plan.get("capabilities"), "capabilities")
    prs = plan.get("prs")
    require(isinstance(prs, list) and prs, "prs: nonempty list required")
    units, covered, branches, worktrees = {}, [], set(), set()
    for pr in prs:
        require(isinstance(pr, dict), "PR must be an object")
        for key in ("id", "reason", "branch", "worktree", "implementer"):
            require(nonempty(pr.get(key)), f"PR {key} required")
        identifier = pr["id"]
        require(identifier not in units, f"duplicate PR id: {identifier}")
        require(pr["branch"] not in branches, "PR branches must be distinct")
        # Normalize paths to catch ./work and work, or symlink aliases.
        worktree = str((Path(repo) / pr["worktree"]).resolve())
        require(worktree not in worktrees, "one writer per worktree; duplicate worktree")
        branches.add(pr["branch"])
        worktrees.add(worktree)
        members = strings(pr.get("capabilities"), f"{identifier} capabilities")
        covered.extend(members)
        strings(pr.get("acceptance"), f"{identifier} acceptance")
        strings(pr.get("tests"), f"{identifier} tests")
        strings(pr.get("depends_on"), f"{identifier} dependencies", empty=True)
        files = strings(pr.get("files"), f"{identifier} files")
        for name in files:
            path = PurePosixPath(name)
            require(path.parts and not path.is_absolute() and str(path) == name and ".." not in path.parts
                    and "\0" not in name
                    and ".git" not in path.parts, f"exact relative file required: {name}")
        if len(members) > 1:
            justified(pr.get("indivisibility"), f"{identifier} separable capabilities",
                      pr["implementer"])
        if "size_exception" in pr:
            justified(pr["size_exception"], f"{identifier} size exception")
        contracts = pr.get("contracts")
        require(isinstance(contracts, list), f"{identifier} contracts list required (empty if none)")
        names = set()
        for contract in contracts:
            require(isinstance(contract, dict), "contract must be an object")
            for key in ("name", "compatibility", "evidence"):
                require(nonempty(contract.get(key)), f"contract {key} required")
            require(contract["name"] not in names, "duplicate contract")
            names.add(contract["name"])
        units[identifier] = pr
    require(len(covered) == len(set(covered)), "capability covered by more than one PR")
    require(set(covered) == set(capabilities), "complete and unique capability coverage required")
    for identifier, pr in units.items():
        require(all(dep in units and dep != identifier for dep in pr["depends_on"]),
                f"{identifier}: unknown or self dependency")
    remaining, done, waves = set(units), set(), []
    while remaining:
        ready = sorted(item for item in remaining
                       if set(units[item]["depends_on"]) <= done)
        require(ready, "dependency cycle")
        wave, occupied = [], set()
        for item in ready:
            files = set(units[item]["files"])
            if not files & occupied:
                wave.append(item)
                occupied |= files
        waves.append(wave)
        remaining -= set(wave)
        done |= set(wave)
    return units, waves


def git(repo, *args):
    result = subprocess.run(["git", "-C", repo, *args], capture_output=True)
    require(result.returncode == 0, f"Git check failed: {args[0]}")
    return result.stdout


def resolve(repo, ref):
    require(nonempty(ref) and not ref.startswith("-") and "\0" not in ref, "invalid Git ref")
    value = git(repo, "rev-parse", "--verify", "--end-of-options", ref + "^{commit}")
    return value.decode().strip()


def ancestor(repo, older, newer):
    result = subprocess.run(["git", "-C", repo, "merge-base", "--is-ancestor", older, newer],
                            capture_output=True)
    require(result.returncode in (0, 1), "Git ancestry check failed")
    return result.returncode == 0


def diff_evidence(repo, base, head):
    raw = git(repo, "diff", "--no-ext-diff", "--no-textconv", "--no-relative",
              "--ignore-submodules=none", "--name-status", "-z",
              "--find-renames", base, head, "--").split(b"\0")
    changes, paths, index = [], set(), 0
    while index < len(raw) - 1:
        status = raw[index].decode()
        count = 2 if status.startswith(("R", "C")) else 1
        names = [name.decode("utf-8", "surrogateescape")
                 for name in raw[index + 1:index + 1 + count]]
        require(len(names) == count and all(names), "invalid Git name-status output")
        changes.append({"status": status, "paths": names})
        paths.update(names)
        index += count + 1
    stats = git(repo, "diff", "--no-ext-diff", "--no-textconv", "--no-relative",
                "--ignore-submodules=none", "--numstat", "-z",
                "--find-renames", base, head, "--").split(b"\0")
    lines, binaries, index = 0, [], 0
    while index < len(stats) - 1:
        added, removed, name = stats[index].split(b"\t", 2)
        index += 1
        names = [name] if name else stats[index:index + 2]
        if not name:
            index += 2
        if added == b"-" or removed == b"-":
            binaries.extend(item.decode("utf-8", "surrogateescape") for item in names)
        else:
            lines += int(added) + int(removed)
    binary_sizes = []
    for path in sorted(set(binaries)):
        sizes = {}
        for label, ref in (("base", base), ("head", head)):
            # ls-tree literal path, no ambiguous ref:path parsing or external filters.
            entry = git(repo, "--literal-pathspecs", "ls-tree", "-z", ref, "--", path)
            if entry:
                metadata = entry.split(b"\t", 1)[0].split()
                sizes[label] = int(git(repo, "cat-file", "-s", metadata[2].decode()))
            else:
                sizes[label] = 0
        binary_sizes.append({"path": path, **sizes})
    return {"changes": changes, "paths": sorted(paths), "files": len(changes),
            "lines": lines, "binaries": binary_sizes}


def check_deliverables(review, evidence):
    """Require independent purpose evidence; do not infer intent from extensions."""
    for change in evidence["changes"]:
        if change["status"] == "D":
            continue  # Allow cleanup of previously committed local artifacts.
        for name in change["paths"]:
            parts = PurePosixPath(name).parts
            require(".agentic-local" not in parts
                    and name != "docs/agentic/STATUS.md"
                    and not (name == "docs/agentic/work" or name.startswith("docs/agentic/work/")),
                    f"local process artifact in PR: {name}")
    findings = review.get("deliverables")
    require(isinstance(findings, list), "per-file deliverable reviews required")
    names = []
    for item in findings:
        require(isinstance(item, dict) and nonempty(item.get("path")),
                "deliverable path required")
        name = item["path"]
        require(item.get("role") in ("production", "test") and item.get("pass") is True
                and nonempty(item.get("evidence")),
                f"production or associated test evidence required: {name}")
        names.append(name)
    require(len(names) == len(set(names)) and set(names) == set(evidence["paths"]),
            "review must justify every changed path exactly once, including rename sources")


def check_review(review, pr, digest, base, head, target, evidence):
    require(isinstance(review, dict), "review must be an object")
    require(review.get("pr") == pr["id"] and review.get("plan_sha256") == digest
            and review.get("base") == base and review.get("head") == head
            and review.get("target") == target,
            "stale review: PR, plan hash and base/head/target must match")
    require(nonempty(review.get("reviewer")) and review["reviewer"] != pr["implementer"],
            "independent semantic reviewer required")
    require(review.get("verdict") == "PASS", "semantic review must PASS")
    check_deliverables(review, evidence)
    for key in ("scope", "no_independent_changes", "size", "indivisibility"):
        finding = review.get(key)
        require(isinstance(finding, dict) and finding.get("pass") is True
                and nonempty(finding.get("evidence")), f"explicit semantic review required: {key}")
    findings = review.get("contracts")
    require(isinstance(findings, list), "contract reviews required")
    expected = {item["name"] for item in pr["contracts"]}
    names = []
    for item in findings:
        require(isinstance(item, dict) and item.get("pass") is True
                and nonempty(item.get("evidence")), "contract compatibility must PASS with evidence")
        names.append(item.get("name"))
    require(len(names) == len(set(names)) and set(names) == expected,
            "review must cover every contract exactly once")
    findings = review.get("dependencies")
    require(isinstance(findings, list), "dependency reviews required (empty if none)")
    identifiers = []
    for item in findings:
        require(isinstance(item, dict) and item.get("pass") is True
                and nonempty(item.get("evidence")), "dependency identity must PASS with evidence")
        identifiers.append(item.get("pr"))
    require(len(identifiers) == len(set(identifiers))
            and set(identifiers) == set(pr["depends_on"]),
            "review must identify every merged dependency exactly once")


def ship(args, plan, units, digest, result):
    require(args.pr in units, "unknown --pr")
    require(all((args.base, args.head, args.target, args.review)),
            "ship requires --pr --base --head --target --review")
    pr = units[args.pr]
    base, head, target = [resolve(args.repo, ref) for ref in (args.base, args.head, args.target)]
    snapshot = {"base": base, "head": head, "target": target, "dependencies": []}
    result["evidence"] = snapshot
    actual_base = git(args.repo, "merge-base", target, head).decode().strip()
    snapshot["actual_base"] = actual_base
    require(base == actual_base, "base must be actual merge-base of target/head; rebase stacked PR")
    require(base != head, "empty PR")
    evidence = diff_evidence(args.repo, base, head)
    snapshot["diff"] = evidence
    dependencies = []
    pending = list(pr["depends_on"])
    while pending:
        identifier = pending.pop(0)
        if identifier in dependencies:
            continue
        dependencies.append(identifier)
        pending.extend(units[identifier]["depends_on"])
        commit = units[identifier].get("merged_commit")
        require(isinstance(commit, str) and re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit),
                f"{identifier}: exact merged_commit required before Ship")
        merged = resolve(args.repo, commit)
        require(ancestor(args.repo, merged, target), f"{identifier}: dependency not merged in target")
        snapshot["dependencies"].append({"pr": identifier, "merged_commit": merged})
    require(set(evidence["paths"]) <= set(pr["files"]),
            "out of scope files: " + ", ".join(sorted(set(evidence["paths"]) - set(pr["files"]))))
    oversized = evidence["files"] > 3 or evidence["lines"] > 100 or bool(evidence["binaries"])
    snapshot["size_exception_required"] = oversized
    if oversized:
        justified(pr.get("size_exception"), "actual size exceeds targets or includes binary")
    check_review(load_json(args.review), pr, digest, base, head, target, evidence)
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("split", "ship"))
    parser.add_argument("manifest")
    parser.add_argument("--repo", default=".")
    for name in ("pr", "base", "head", "target", "review"):
        parser.add_argument("--" + name)
    args = parser.parse_args()
    result = {"gate": "PR_SPLIT" if args.mode == "split" else "PR_SCOPE", "verdict": "BLOCKED"}
    try:
        plan = load_json(args.manifest)
        args.repo = git(args.repo, "rev-parse", "--show-toplevel").decode().strip()
        units, waves = check_plan(plan, args.repo)
        digest = plan_hash(plan)
        result.update(plan_sha256=digest, waves=waves, merge_order=[item for wave in waves for item in wave])
        if args.mode == "ship":
            result["evidence"] = ship(args, plan, units, digest, result)
        result.update(verdict="PASS", reason="Declared boundaries and required evidence validated")
    except (Blocked, OSError, ValueError, TypeError, KeyError) as error:
        result["reason"] = str(error)
    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
