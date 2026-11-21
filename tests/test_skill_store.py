"""Project-local skill lifecycle, tested against fixed bytes without network."""
import copy
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
from pathlib import Path
import sqlite3
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/agentic-skill-store.py"
SPEC = importlib.util.spec_from_file_location("skill_store", SCRIPT)
STORE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STORE)
FETCH = STORE._fetch


def digest(data):
    return hashlib.sha256(data).hexdigest()


class StoreTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.repo = Path(temp.name)
        subprocess.run(["git", "init", "-q", self.repo], check=True)
        self.source = b"---\nname: fixture\n---\nuseful text\nignored command\nnext line\n"
        self.body = b"useful text\n\nnext line\n"
        self.terms = b"MIT\nCopyright Example\nPermission notice retained.\n"
        self.entry = dict(id="example/demo", repo="example/demo", commit="a"*40,
                          name="demo", status="approved", agents=["codex", "claude"],
                          description="Demo", category="quality", capability="debug",
                          risks="text only", priority=1, triggers=[["debug"]], excludes=[],
                          files=[], path="demo/SKILL.md", terms="LICENSE", license="MIT",
                          ranges=[[4,4],[6,6]], depends_on=[], extracted_sha256=digest(self.body),
                          files_sha256={"demo/SKILL.md": digest(self.source),
                                        "LICENSE": digest(self.terms)})
        self.catalog = {"version": 1, "skills": [self.entry], "discovery": []}
        self.fetch = patch.object(STORE, "_fetch", side_effect=self.fixture).start()
        self.addCleanup(patch.stopall)

    def fixture(self, entry, path):
        return self.source if path.endswith("SKILL.md") else self.terms

    def run_action(self, action, skill_id="example/demo", **options):
        return STORE.manage(action, self.repo, skill_id, catalog=self.catalog, **options)

    def load(self, **overrides):
        options = {"agent": "codex", "expect": digest(self.body), **overrides}
        return self.run_action("load", **options)

    def inventory(self):
        return STORE.inventory(self.repo, self.catalog)

    def test_inventory_is_read_only_and_dependency_free(self):
        with patch.object(STORE, "_fetch", side_effect=AssertionError("network")):
            before = list((self.repo / ".git").iterdir())
            row, = self.inventory()
            self.assertFalse(row["installed"])
            self.assertFalse(row["available"])
            self.assertTrue(row["enabled"])
            self.assertEqual(before, list((self.repo / ".git").iterdir()))
        self.run_action("install")
        with patch.object(STORE, "_fetch", side_effect=AssertionError("network")):
            self.run_action("install")
            row, = self.inventory()
            self.assertTrue(row["available"])
            self.assertNotIn("useful text", json.dumps(row))
            self.assertEqual(row["installed_commit"], self.entry["commit"])
            loaded = self.load()
            self.assertEqual(loaded["instructions"].encode(), self.body)
            self.assertEqual(loaded["applied"], "NOT_OBSERVED")
            self.assertEqual(loaded["commit"], self.entry["commit"])
            self.assertEqual(loaded["state"], "LOADED")
            self.assertNotIn("ignored command", json.dumps(loaded))
        self.run_action("uninstall")
        self.assertFalse(self.inventory()[0]["installed"])

    def test_compatibility_disabled_and_stale_pin_fail_closed(self):
        self.run_action("install")
        for mismatch in [{"agent": "unregistered"}, {"expect": "f"*64}, {"expect": ""}]:
            with self.subTest(mismatch=mismatch), self.assertRaises(ValueError):
                self.load(**mismatch)
        self.run_action("disable")
        self.assertFalse(self.inventory()[0]["enabled"])
        with self.assertRaises(ValueError):
            self.load()
        self.run_action("update")
        self.assertFalse(self.inventory()[0]["enabled"])
        self.run_action("enable")
        self.assertIn("useful", self.load()["instructions"])
        self.entry["status"] = "blocked"
        self.assertFalse(self.inventory()[0]["available"])
        with self.assertRaises(ValueError):
            self.load()

    def test_explicit_update_or_rollback_never_overwrites_another_origin(self):
        self.run_action("install")
        original = self.entry["commit"]
        self.entry["commit"] = "b"*40
        self.assertFalse(self.inventory()[0]["available"])
        with self.assertRaises(ValueError):
            self.run_action("install")
        self.run_action("update")
        self.assertEqual(self.load()["commit"], "b"*40)
        self.entry["commit"] = original
        self.run_action("update")
        self.assertEqual(self.load()["commit"], original)
        self.entry["repo"] = "somewhere/else"
        with self.assertRaises(ValueError):
            self.run_action("update")

    def test_dep_graph_atomic_and_missing_blocked_or_cyclic_dependency_refused(self):
        dep = copy.deepcopy(self.entry)
        dep["id"] = "example/base"
        self.entry["depends_on"] = [dep["id"]]
        with self.assertRaises(ValueError):
            self.run_action("install")
        self.catalog["skills"].append(dep)
        dep["depends_on"] = [self.entry["id"]]
        with self.assertRaises(ValueError):
            self.run_action("install")
        dep["depends_on"] = []
        dep["status"] = "blocked"
        with self.assertRaises(ValueError):
            self.run_action("install")
        dep["status"] = "approved"
        def failing_fetch(entry, path):
            if entry["id"] == self.entry["id"]:
                return b"wrong bytes"
            return self.fixture(entry, path)
        self.fetch.side_effect = failing_fetch
        with self.assertRaises(ValueError):
            self.run_action("install")
        self.assertFalse(any(r["installed"] for r in self.inventory()))
        self.fetch.side_effect = self.fixture
        self.run_action("install")
        self.assertTrue(all(r["available"] for r in self.inventory()))
        with self.assertRaises(ValueError):
            self.run_action("uninstall", dep["id"])
        self.run_action("disable", dep["id"])
        self.assertFalse(self.inventory()[0]["available"])
        with self.assertRaises(ValueError):
            self.load()

    def test_wrong_digests_source_license_or_projection_block_install(self):
        for field in ("source", "license", "extracted"):
            entry = copy.deepcopy(self.entry)
            with self.subTest(field=field):
                if field == "extracted":
                    self.entry["extracted_sha256"] = "0"*64
                else:
                    self.entry["files_sha256"]["LICENSE" if field=="license" else "demo/SKILL.md"] = "0"*64
                with self.assertRaises(ValueError):
                    self.run_action("install")
                self.entry.update(entry)
                self.assertFalse(self.inventory()[0]["installed"])

    def test_corrupt_persisted_blob_refused_on_load_and_update(self):
        self.run_action("install")
        db = sqlite3.connect(STORE.database_path(self.repo))
        with db:
            db.execute("UPDATE installed SET instructions=?", (b"tampered",))
        db.close()
        for action in [self.load, lambda: self.run_action("update")]:
            with self.assertRaises(ValueError):
                action()

    def test_reject_duplicate_ids_nonimmutable_urls_and_excluded_origins_before_fetch(self):
        for field, value in [("repo", "obra/superpowers"), ("repo", "h/user?path=x"),
                             ("repo", "ComposioHQ/awesome-claude-skills"), ("commit", "main"),
                             ("path", "../SKILL.md"), ("terms", "../../NOTICE")]:
            original = self.entry[field]
            self.entry[field] = value
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                self.run_action("install")
            self.entry[field] = original
        self.catalog["skills"].append(copy.deepcopy(self.entry))
        with self.assertRaises(ValueError):
            self.run_action("install")
        self.fetch.assert_not_called()

    def test_symlink_collision_and_run_concurrently(self):
        path = STORE.database_path(self.repo)
        path.parent.mkdir(parents=True, exist_ok=True)
        target = self.repo / "personal"
        target.write_bytes(b"intact")
        path.symlink_to(target)
        with self.assertRaises((OSError, ValueError)):
            self.run_action("install")
        self.assertEqual(target.read_bytes(), b"intact")
        path.unlink()
        path.parent.rmdir()
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: self.run_action("install"), range(2)))
        self.assertEqual(self.load()["instructions"].encode(), self.body)

    def test_pin_commit_and_data_shared_only_within_same_git_common_dir(self):
        self.run_action("install")
        self.assertEqual(self.load(commit=self.entry["commit"])["commit"], self.entry["commit"])
        with self.assertRaises(ValueError):
            self.load(commit="f" * 40)
        subprocess.run(["git", "-C", self.repo, "-c", "user.name=Test", "-c",
                        "user.email=t@example.invalid", "commit", "--allow-empty", "-qm", "base"],
                       check=True)
        linked = self.repo / "worktree"
        subprocess.run(["git", "-C", self.repo, "worktree", "add", "-q", "--detach", linked],
                       check=True)
        self.assertEqual(self.inventory(), STORE.inventory(linked, self.catalog))
        self.assertEqual(STORE.manage("load", linked, self.entry["id"], catalog=self.catalog,
                                    agent="claude", expect=digest(self.body))["state"], "LOADED")
        another = self.repo / "another"
        subprocess.run(["git", "init", "-q", another], check=True)
        self.assertFalse(STORE.inventory(another, self.catalog)[0]["installed"])

    def test_ordinary_db_at_store_location_remains_untouched(self):
        path = STORE.database_path(self.repo)
        path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(path) as existing:
            existing.execute("CREATE TABLE my_files (name text)")
        before = path.read_bytes()
        with self.assertRaises((ValueError, sqlite3.DatabaseError)):
            self.run_action("install")
        self.assertEqual(path.read_bytes(), before)

    def test_orphan_remains_visible_and_can_be_removed(self):
        self.run_action("install")
        self.catalog["skills"].clear()
        row, = self.inventory()
        self.assertTrue(row["installed"])
        self.assertFalse(row["available"])
        self.assertEqual(row["status"], "removed")
        self.run_action("uninstall")
        self.assertEqual(self.inventory(), [])

    def test_compatibility_applies_to_whole_graph(self):
        dep = copy.deepcopy(self.entry)
        dep.update(id="example/base", agents=["claude"])
        self.entry["depends_on"] = [dep["id"]]
        self.catalog["skills"].append(dep)
        self.run_action("install")
        self.assertEqual(self.inventory()[0]["agents"], ["claude"])
        with self.assertRaises(ValueError):
            self.load(agent="codex")
        self.assertEqual(self.load(agent="claude")["state"], "LOADED")

    def test_projection_preserves_unicode_line_separators_and_crlf_bytes(self):
        raw = "a\u2028b\r\nc\r\nd".encode("utf-8")
        self.assertEqual(STORE._extract(raw, [[1, 1], [3, 3]]), "a\u2028b\r\n\nd".encode())

    def test_cli_inventory_then_load_share_project_install(self):
        tool_dir = self.repo / "method/scripts"
        tool_dir.mkdir(parents=True)
        skill_dir = self.repo / "method/skills"
        skill_dir.mkdir()
        script = tool_dir / SCRIPT.name
        shutil.copy(SCRIPT, script)
        (skill_dir / "catalog.json").write_text(json.dumps(self.catalog))
        def cli(*args):
            return subprocess.run(["python3", str(script), *args, "--repo", self.repo],
                                  capture_output=True, text=True)
        self.assertFalse(json.loads(cli("inventory").stdout)[0]["installed"])
        self.run_action("install")
        result = cli("load", self.entry["id"], "--expect", digest(self.body), "--commit",
                     self.entry["commit"], "--agent", "codex")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["instructions"].encode(), self.body)
        self.assertEqual(cli("disable", self.entry["id"]).returncode, 0)
        result = cli("load", self.entry["id"], "--expect", digest(self.body), "--agent", "codex")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("error", json.loads(result.stdout))

    def test_transport_only_contacts_raw_origin_and_refuses_redirect_and_oversize(self):
        with patch.object(STORE.http.client, "HTTPSConnection") as connect:
            connection = connect.return_value
            response = connection.getresponse.return_value.__enter__.return_value
            response.status = 302
            with self.assertRaises(ValueError):
                FETCH(self.entry, self.entry["path"])
            response.read1.assert_not_called()
            connect.assert_called_once_with("raw.githubusercontent.com", timeout=10)
            connection.request.assert_called_once_with(
                "GET", "/example/demo/" + self.entry["commit"] + "/demo/SKILL.md")
            response.status = 200
            response.read1.side_effect = lambda size: b"x" * size
            with self.assertRaises(ValueError):
                FETCH(self.entry, self.entry["path"])
