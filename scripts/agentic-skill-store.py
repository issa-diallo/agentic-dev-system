#!/usr/bin/env python3
"""Keep audited skill excerpts in a transactional, project-local Git store."""
import argparse
from contextlib import closing, contextmanager
import errno
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import sqlite3
import stat
import subprocess
import tempfile
import time

CATALOG = Path(__file__).resolve().parents[1] / "skills/catalog.json"
MAX_BYTES = 1024 * 1024
APPLICATION_ID = 0x41534B31  # ASK1
ID = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*/[a-z0-9]+(?:-[a-z0-9]+)*")
REPO = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9][A-Za-z0-9._-]*")
SEGMENT = re.compile(r"(?:[A-Za-z0-9_-]|\.[A-Za-z0-9_-])[A-Za-z0-9._-]*")
HEX = re.compile(r"[0-9a-f]{64}")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def _catalog(catalog):
    if catalog is None:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    if catalog["version"] != 1:
        raise ValueError("unsupported skill catalog")
    entries = {}
    for entry in catalog["skills"]:
        key = entry["id"]
        if not ID.fullmatch(key) or key in entries:
            raise ValueError("invalid or duplicate skill id")
        if "superpowers" in " ".join(str(entry.get(k, "")) for k in
                                     ("id", "repo", "path", "terms", "name")).casefold():
            raise ValueError("excluded skill origin")
        if entry["repo"].casefold() == "composiohq/awesome-claude-skills":
            raise ValueError("discovery-only source")
        if entry["status"] not in ("approved", "blocked"):
            raise ValueError("unknown approval state")
        if entry["status"] == "approved":
            _validate_source(entry)
        entries[key] = entry
    return entries


def _validate_source(entry):
    if not REPO.fullmatch(entry["repo"]) or not re.fullmatch(r"[0-9a-f]{40}", entry["commit"]):
        raise ValueError("invalid immutable GitHub source")
    path, terms = entry["path"], entry["terms"]
    for filename in (path, terms):
        if not all(SEGMENT.fullmatch(part) for part in filename.split("/")):
            raise ValueError("invalid source path")
    if path.split("/")[-1] != "SKILL.md" or not re.fullmatch(
        r"(LICENSE|LICENCE|COPYING|NOTICE|README)(\.(md|txt))?", terms.split("/")[-1], re.I
    ):
        raise ValueError("expected skill and license documents")
    hashes = entry["files_sha256"]
    if (set(hashes) != {path, terms} or not entry["license"]
            or not all(HEX.fullmatch(h) for h in (*hashes.values(), entry["extracted_sha256"]))):
        raise ValueError("missing source, license or excerpt digest")
    if not isinstance(entry["agents"], list) or not entry["agents"]:
        raise ValueError("expected compatible agents")
    if not isinstance(entry["depends_on"], list) or not all(ID.fullmatch(k) for k in entry["depends_on"]):
        raise ValueError("invalid skill dependencies")


def _closure(entries, root):
    """Dependencies are installed and validated before their consumer."""
    done, visiting = [], set()

    def visit(key):
        if key not in entries or entries[key]["status"] != "approved":
            raise ValueError("unapproved or unknown skill: " + key)
        if key in visiting:
            raise ValueError("cyclic skill dependency")
        if key not in done:
            visiting.add(key)
            for dependency in entries[key]["depends_on"]:
                visit(dependency)
            visiting.remove(key)
            done.append(key)

    visit(root)
    return done


def database_path(repo):
    """Linked Git worktrees share their primary checkout's private database."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    result = subprocess.run(
        ["git", "-C", str(Path(repo).resolve(strict=True)), "rev-parse", "--path-format=absolute",
         "--show-toplevel", "--git-common-dir", "--git-dir"], env=env,
        capture_output=True, text=True, check=True)
    root, common, git_dir = map(Path, result.stdout.splitlines())
    dotgit = root / ".git"
    if dotgit.is_symlink() or common != common.resolve(strict=True):
        raise ValueError("unsafe Git metadata path")
    if common != dotgit:
        # A .git pointer to an unrelated repository does not grant write access to it.
        marker = git_dir / "gitdir"
        if (git_dir.parent != common / "worktrees" or not dotgit.is_file()
                or not marker.is_file() or marker.is_symlink()
                or (git_dir / marker.read_text().strip()).resolve() != dotgit):
            raise ValueError("unregistered linked worktree")
    return common / "agentic-skill-store" / "v1.sqlite3"


def _check_files(path):
    if path.parent.is_symlink() or (path.parent.exists() and not path.is_file()):
        raise ValueError("unmanaged or unsafe skill store directory")
    for suffix in ("", "-journal", "-shm", "-wal"):
        candidate = Path(str(path) + suffix)
        try:
            info = candidate.lstat()
        except FileNotFoundError:
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError("unsafe skill database path: " + candidate.name)


def _initialize(path):
    # Publish a complete database without overwriting another concurrent install.
    with tempfile.TemporaryDirectory(dir=path.parent.parent) as temp:
        stage = Path(temp) / "store"
        stage.mkdir(mode=0o700)
        with closing(sqlite3.connect(stage / path.name)) as db:
            db.executescript(f"""
                PRAGMA application_id={APPLICATION_ID};
                CREATE TABLE installed (
                    id TEXT PRIMARY KEY, origin TEXT, path TEXT, revision TEXT, pin TEXT,
                    digest TEXT, terms_digest TEXT, dependencies TEXT,
                    instructions BLOB, notice BLOB);
                CREATE TABLE disabled (id TEXT PRIMARY KEY);
            """)
        try:
            stage.rename(path.parent)
        except OSError as exc:
            if exc.errno not in (errno.EEXIST, errno.ENOTEMPTY):
                raise
        _check_files(path)


@contextmanager
def _database(repo, write=False):
    path = database_path(repo)
    _check_files(path)
    if not path.exists():
        if not write:
            yield None
            return
        _initialize(path)
    uri = path.as_uri() + ("?mode=rw" if write else "?mode=ro")
    with closing(sqlite3.connect(uri, uri=True, timeout=30)) as db, db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA trusted_schema=OFF")
        if db.execute("PRAGMA application_id").fetchone()[0] != APPLICATION_ID:
            raise ValueError("unmanaged database collision")
        db.execute("BEGIN IMMEDIATE" if write else "BEGIN")
        yield db


def _fetch(entry, path):
    """No redirects, proxies, environment credentials, cookies or third-party CLI."""
    route = "/" + "/".join((entry["repo"], entry["commit"], path))
    deadline = time.monotonic() + 30
    with closing(http.client.HTTPSConnection("raw.githubusercontent.com", timeout=10)) as conn:
        conn.request("GET", route)
        with conn.getresponse() as response:
            if response.status != 200:
                raise ValueError(f"GitHub raw request failed (HTTP {response.status})")
            data = bytearray()
            while len(data) <= MAX_BYTES and time.monotonic() < deadline:
                chunk = response.read1(min(65536, MAX_BYTES + 1 - len(data)))
                if not chunk:
                    return bytes(data)
                data.extend(chunk)
            raise ValueError("remote file exceeded size or time limit")


def _extract(raw, ranges):
    lines = raw.splitlines(keepends=True)
    previous, parts = 0, []
    for start, end in ranges:
        if not (type(start) is int and type(end) is int and previous < start <= end <= len(lines)):
            raise ValueError("invalid reviewed line ranges")
        parts.append(b"".join(lines[start-1:end]))
        previous = end
    if not parts:
        raise ValueError("empty reviewed excerpt")
    result = b"\n".join(parts)
    result.decode("utf-8")
    return result


def _pin(entry):
    fields = ("repo", "commit", "path", "terms", "license", "files_sha256", "ranges",
              "terms_ranges", "extracted_sha256", "depends_on")
    return digest(json.dumps([entry.get(k) for k in fields], sort_keys=True).encode())


def _metadata(db):
    if db is None:
        return {}, set()
    rows = db.execute("SELECT id, origin, path, revision, pin, dependencies FROM installed")
    return {r["id"]: r for r in rows}, {r[0] for r in db.execute("SELECT id FROM disabled")}


def _available(entries, key, rows, disabled):
    try:
        chain = _closure(entries, key)
    except ValueError:
        return False
    for k in chain:
        row, entry = rows.get(k), entries[k]
        if (not row or k in disabled or row["pin"] != _pin(entry)
                or (row["origin"], row["path"], row["revision"])
                != (entry["repo"], entry["path"], entry["commit"])
                or json.loads(row["dependencies"]) != entry["depends_on"]):
            return False
    return True


def inventory(repo, catalog=None):
    entries = _catalog(catalog)
    with _database(repo) as db:
        rows, disabled = _metadata(db)
        result = []
        for k, entry in entries.items():
            try:
                chain = _closure(entries, k)
                agents = [a for a in entry["agents"] if all(a in entries[j]["agents"] for j in chain)]
            except ValueError:
                agents = []
            result.append({**entry, "declared_agents": entry["agents"], "agents": agents,
                           "installed": k in rows, "enabled": k not in disabled,
                           "available": bool(agents) and _available(entries, k, rows, disabled),
                           "installed_commit": rows[k]["revision"] if k in rows else None})
        for k in sorted(rows.keys() - entries.keys()):
            row = rows[k]
            result.append({"id": k, "repo": row["origin"], "path": row["path"],
                           "installed_commit": row["revision"], "installed": True,
                           "enabled": k not in disabled, "available": False,
                           "status": "removed", "agents": []})
        return result


def _verified_data(db, key):
    row = db.execute("SELECT instructions, notice, digest, terms_digest FROM installed WHERE id=?",
                     (key,)).fetchone()
    if row is None or (digest(row["instructions"]) != row["digest"]
                       or digest(row["notice"]) != row["terms_digest"]):
        raise ValueError("altered local skill or license: " + key)
    return row


def _install(db, entry, prior, updating):
    key = entry["id"]
    if prior:
        if (prior["origin"], prior["path"]) != (entry["repo"], entry["path"]):
            raise ValueError("skill id collision with installed origin: " + key)
        old = _verified_data(db, key)
        if prior["pin"] == _pin(entry):
            if (old["digest"] != entry["extracted_sha256"]
                    or old["terms_digest"] != entry["files_sha256"][entry["terms"]]):
                raise ValueError("installed content differs from reviewed catalog")
            return
        if not updating:
            raise ValueError("different catalog pin; use update: " + key)
    files = {}
    for path, expected in entry["files_sha256"].items():
        raw = _fetch(entry, path)
        if len(raw) > MAX_BYTES or digest(raw) != expected:
            raise ValueError("upstream integrity mismatch: " + path)
        files[path] = raw
    body = _extract(files[entry["path"]], entry["ranges"])
    notice = files[entry["terms"]]
    if entry.get("terms_ranges"):
        _extract(notice, entry["terms_ranges"])  # Validate notice boundaries before install.
    else:
        notice.decode("utf-8")
    if digest(body) != entry["extracted_sha256"]:
        raise ValueError("reviewed excerpt integrity mismatch: " + key)
    db.execute("INSERT OR REPLACE INTO installed VALUES (?,?,?,?,?,?,?,?,?,?)",
               (key, entry["repo"], entry["path"], entry["commit"], _pin(entry),
                digest(body), digest(notice), json.dumps(entry["depends_on"]), body, notice))


def manage(action, repo, skill_id, *, catalog=None, agent=None, expect=None, commit=None):
    entries = _catalog(catalog)
    if not ID.fullmatch(skill_id) or "superpowers" in skill_id:
        raise ValueError("invalid or excluded skill id")
    loading = action == "load"
    with _database(repo, write=not loading) as db:
        rows, disabled = _metadata(db)
        if action == "uninstall":
            for row in rows.values():
                if skill_id in json.loads(row["dependencies"]):
                    raise ValueError("installed dependent: " + row["id"])
            db.execute("DELETE FROM installed WHERE id=?", (skill_id,))
            db.execute("DELETE FROM disabled WHERE id=?", (skill_id,))
        elif action in ("install", "update"):
            for key in _closure(entries, skill_id):
                _install(db, entries[key], rows.get(key), action == "update")
        elif action in ("enable", "disable"):
            if skill_id not in entries and skill_id not in rows:
                raise ValueError("unknown skill")
            if action == "enable":
                db.execute("DELETE FROM disabled WHERE id=?", (skill_id,))
            else:
                db.execute("INSERT OR IGNORE INTO disabled VALUES (?)", (skill_id,))
        elif loading:
            chain = _closure(entries, skill_id)
            entry = entries[skill_id]
            if (not _available(entries, skill_id, rows, disabled)
                    or any(agent not in entries[k]["agents"] for k in chain)
                    or entry["extracted_sha256"] != expect
                    or (commit is not None and entry["commit"] != commit)):
                raise ValueError("unavailable, incompatible or stale skill reference")
            for key in chain:
                pinned = entries[key]
                verified = _verified_data(db, key)
                if (verified["digest"] != pinned["extracted_sha256"] or
                        verified["terms_digest"] != pinned["files_sha256"][pinned["terms"]]):
                    raise ValueError("installed content differs from reviewed catalog")
            return {"id": skill_id, "state": "LOADED", "applied": "NOT_OBSERVED", "agent": agent,
                    "sha256": expect, "repo": entry["repo"], "commit": entry["commit"],
                    "path": entry["path"], "ranges": entry["ranges"], "license": entry["license"],
                    "terms": entry["terms"], "instructions": verified["instructions"].decode()}
        else:
            raise ValueError("unknown skill action")
    return {"action": action, "id": skill_id}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="action", required=True)
    for action in ("inventory", "install", "update", "uninstall", "enable", "disable", "load"):
        command = commands.add_parser(action)
        command.add_argument("--repo", required=True, type=Path)
        if action != "inventory":
            command.add_argument("id")
        if action == "load":
            command.add_argument("--agent", required=True)
            command.add_argument("--expect", required=True)
            command.add_argument("--commit")
    args = parser.parse_args()
    try:
        if args.action == "inventory":
            result = inventory(args.repo)
        else:
            options = {k: getattr(args, k) for k in ("agent", "expect", "commit") if hasattr(args, k)}
            result = manage(args.action, args.repo, args.id, **options)
    except (ValueError, KeyError, TypeError, OSError, sqlite3.Error, subprocess.SubprocessError,
            http.client.HTTPException) as error:
        print(json.dumps({"error": str(error)}))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
