#!/usr/bin/env python3
"""Execute trusted argv checks and assess fresh evidence; no shell or agent auth.

Commands and review/runtime attestations must come from the orchestrator. JSON
names cannot authenticate agents. Output is represented only by hashes, never
raw logs. This gate does not sandbox processes or authorize external actions.
"""
import argparse
import hashlib
import json
import os
import signal
import threading
from pathlib import Path
import subprocess


def git(repo, *args):
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True)
    if result.returncode:
        raise ValueError("Git inspection failed")
    return result.stdout


def root(repo):
    path = Path(repo).resolve()
    actual = Path(git(path, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    if actual != path:
        raise ValueError("cwd must be an actual Git worktree root")
    return path


def snapshot(repo):
    repo = root(repo)
    head = git(repo, "rev-parse", "HEAD").decode().strip()
    digest = hashlib.sha256()
    for value in (head.encode(), git(repo, "status", "--porcelain=v1", "-z", "-uall"),
                  git(repo, "diff", "--no-ext-diff", "--no-textconv", "--no-relative",
                      "--ignore-submodules=none", "--binary", "HEAD", "--"),
                  git(repo, "diff", "--no-ext-diff", "--no-textconv", "--no-relative",
                      "--ignore-submodules=none", "--binary", "--cached", "HEAD", "--")):
        digest.update(len(value).to_bytes(8, "big"))
        digest.update(value)
    for name in sorted(git(repo, "ls-files", "--others", "--exclude-standard", "-z").split(b"\0")):
        if not name:
            continue
        path = repo / name.decode("utf-8", "surrogateescape")
        value = str(path.readlink()).encode() if path.is_symlink() else path.read_bytes()
        digest.update(len(name).to_bytes(8, "big"))
        digest.update(name)
        digest.update(len(value).to_bytes(8, "big"))
        digest.update(value)
    return {"head": head, "digest": digest.hexdigest()}


def run_checks(repo, commands, timeout=60):
    """Run explicit trusted argv; never evaluate V1 manifest test descriptions."""
    repo = root(repo)
    if (not isinstance(commands, list) or not commands or
            not all(isinstance(c, list) and c and
                    all(isinstance(a, str) and a and "\0" not in a for a in c) for c in commands)):
        raise ValueError("nonempty list of argv arrays required")
    if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout <= 3600:
        raise ValueError("timeout must be positive and at most 3600 seconds")
    before, checks = snapshot(repo), []
    for command in commands:
        timed_out, code, exceeded = False, None, threading.Event()
        hashes = [hashlib.sha256(), hashlib.sha256()]
        process = None

        def stop():
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass

        def consume(stream, digest):
            size = 0
            with stream:
                while chunk := stream.read(8192):
                    size += len(chunk)
                    digest.update(chunk)
                    if size > 1024 * 1024:
                        exceeded.set()
                        stop()
                        break
        try:
            process = subprocess.Popen(command, cwd=repo, stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, start_new_session=True)
            readers = [threading.Thread(target=consume, args=(stream, digest))
                       for stream, digest in zip((process.stdout, process.stderr), hashes)]
            for reader in readers:
                reader.start()
            try:
                code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                stop()
                process.wait()
            # Also stop descendant processes retaining stdout after the parent exits.
            stop()
            for reader in readers:
                reader.join()
        except OSError:
            pass
        checks.append({"command_sha256": hashlib.sha256(json.dumps(command).encode()).hexdigest(),
                       "returncode": code, "timed_out": timed_out,
                       "output_limit_exceeded": exceeded.is_set(),
                       "output_sha256": hashlib.sha256(
                           b"".join(d.digest() for d in hashes)).hexdigest()})
    unchanged = snapshot(repo) == before
    passed = unchanged and all(c["returncode"] == 0 and not c["timed_out"] and
                               not c["output_limit_exceeded"] for c in checks)
    return {"snapshot": before, "checks": checks, "verdict": "PASS" if passed else "BLOCKED",
            "unchanged": unchanged}


def assess(repo, evidence, review, implementer):
    """Assess trusted evidence; provenance must be verified outside this module.

    runtime_evidence.verified_by_orchestrator is that explicit external attestation,
    not independent identity authentication. CI evidence is required for readiness.
    """
    if not isinstance(evidence, dict):
        return "BLOCKED"
    current = snapshot(repo)
    checks = evidence.get("checks", [])
    if (evidence.get("snapshot") != current or evidence.get("verdict") != "PASS" or
            not evidence.get("unchanged") or not isinstance(checks, list) or not checks or
            not all(isinstance(c, dict) and c.get("returncode") == 0 and
                    c.get("timed_out") is False and c.get("output_limit_exceeded") is False and
                    c.get("output_sha256") and
                    c.get("command_sha256") for c in checks)):
        return "BLOCKED"
    if (not isinstance(implementer, str) or not implementer.strip() or
            not isinstance(review, dict) or review.get("snapshot") != current or
            review.get("verdict") not in ("PASS", "PASS_WITH_MINOR") or
            not isinstance(review.get("reviewer"), str) or not review["reviewer"].strip() or
            review["reviewer"] == implementer or
            review.get("implementer", implementer) != implementer or not review.get("evidence")):
        return "BLOCKED"
    provenance = review.get("runtime_evidence", {})
    if (not isinstance(provenance, dict) or provenance.get("verified_by_orchestrator") is not True or
            not provenance.get("agent_id") or provenance["agent_id"] == implementer):
        return "BLOCKED"
    findings = review.get("findings")
    if not isinstance(findings, list):
        return "BLOCKED"
    for finding in findings:
        if (not isinstance(finding, dict) or finding.get("severity") not in
                ("Critical", "Major", "Minor", "Info") or finding.get("status") not in
                ("OPEN", "RESOLVED") or
                (finding["severity"] in ("Critical", "Major") and finding["status"] == "OPEN")):
            return "BLOCKED"
    ci = review.get("ci", {})
    if (not isinstance(ci, dict) or ci.get("source") != "external" or ci.get("status") != "PASS" or
            ci.get("head") != current["head"] or not ci.get("evidence")):
        return "BLOCKED"
    return "PASS"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("run", "assess"))
    parser.add_argument("input", help="Trusted JSON input file; run commands are approved argv")
    args = parser.parse_args()
    try:
        data = json.loads(Path(args.input).read_text())
        if args.mode == "run":
            result = run_checks(data["repo"], data["commands"], data.get("timeout", 60))
        else:
            review = dict(data["review"])
            if "ci" in data:
                if "ci" in review and review["ci"] != data["ci"]:
                    raise ValueError("conflicting CI attestations")
                review["ci"] = data["ci"]
            result = {"verdict": assess(data["repo"], data["evidence"], review, data["implementer"])}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        # JSON parse failures can quote secret input; expose a fixed safe reason.
        result = {"verdict": "BLOCKED", "reason": "Invalid input or inaccessible Git worktree"}
    print(json.dumps(result, sort_keys=True))
    return 0 if result["verdict"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
