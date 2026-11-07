"""Pre-push guard exercised through real `git push` against a real bare remote."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]
SCRIPT = SOURCE / "scripts/agentic-pr-check.py"
MANIFEST = ".agentic-local/docs/agentic/work/7/pr-split.json"


def plan(branch="feat/7-export", files=None):
    pr = {"id": "S7-PR1", "reason": "Export", "capabilities": ["export"],
          "files": files or ["export.py"], "acceptance": ["AC export"], "tests": ["test export"],
          "contracts": [], "depends_on": [], "branch": branch, "worktree": "worktrees/export",
          "implementer": "author"}
    return {"version": 1, "story": "S7", "capabilities": ["export"], "prs": [pr]}


class PushGuardTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        root = Path(self.temporary.name)
        self.remote, self.repo = root / "remote.git", root / "repo"
        subprocess.run(["git", "init", "-q", "--bare", str(self.remote)], check=True)
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        self.git("remote", "add", "origin", str(self.remote))
        (self.repo / ".git/info/exclude").write_text("/.agentic-local/\n")
        self.write("README.md", "base\n")
        self.commit()
        self.git("push", "-q", "origin", "main")
        self.git("fetch", "-q", "origin")
        self.git("checkout", "-q", "-b", "feat/7-export")

    def git(self, *args, check=True, env=None):
        return subprocess.run(["git", "-C", str(self.repo), *args], check=check, text=True,
                              capture_output=True, env={**os.environ, **(env or {})})

    def write(self, name, value):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value)

    def commit(self):
        self.git("add", "--all")
        self.git("commit", "-qm", "work")

    def guard(self, mode):
        return subprocess.run(["python3", str(SCRIPT), mode, "--repo", str(self.repo)],
                              text=True, capture_output=True)

    def push(self, env=None, branch="feat/7-export"):
        return self.git("push", "origin", branch, check=False, env=env)

    def test_push_refused_without_manifest_then_accepted_with_valid_one(self):
        self.assertEqual(self.guard("install-guard").returncode, 0)
        self.write("export.py", "x = 1\n")
        self.commit()
        refused = self.push()
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("run PR_SPLIT first", refused.stdout + refused.stderr)
        self.write(MANIFEST, json.dumps(plan()))
        accepted = self.push()
        self.assertEqual(accepted.returncode, 0, accepted.stderr)

    def test_push_refused_when_a_file_is_outside_the_declared_pr(self):
        self.guard("install-guard")
        self.write(MANIFEST, json.dumps(plan()))
        self.write("export.py", "x = 1\n")
        self.write("unrelated.py", "y = 2\n")
        self.commit()
        refused = self.push()
        self.assertNotEqual(refused.returncode, 0)
        self.assertIn("unrelated.py", refused.stdout + refused.stderr)

    def test_bypass_is_explicit_and_visible(self):
        self.guard("install-guard")
        self.write("export.py", "x = 1\n")
        self.commit()
        result = self.push(env={"AGENTIC_SKIP_PUSH_GUARD": "1"})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("bypassed", result.stderr)

    def test_main_branch_passes_through(self):
        self.guard("install-guard")
        self.git("checkout", "-q", "main")
        self.write("README.md", "changed\n")
        self.commit()
        self.assertEqual(self.push(branch="main").returncode, 0)

    def test_existing_foreign_hook_is_preserved(self):
        hook = self.repo / ".git/hooks/pre-push"
        hook.write_text("#!/bin/sh\nexit 0\n")
        result = self.guard("install-guard")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(hook.read_text(), "#!/bin/sh\nexit 0\n")
        self.assertNotEqual(self.guard("uninstall-guard").returncode, 0)
        self.assertTrue(hook.exists())

    def test_install_is_idempotent_and_uninstall_removes_only_ours(self):
        hook = self.repo / ".git/hooks/pre-push"
        self.guard("install-guard")
        self.assertEqual(self.guard("install-guard").returncode, 0)
        self.assertTrue(hook.exists())
        self.assertEqual(self.guard("uninstall-guard").returncode, 0)
        self.assertFalse(hook.exists())

    def test_custom_hooks_path_is_refused(self):
        self.git("config", "core.hooksPath", "shared-hooks")
        result = self.guard("install-guard")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("core.hooksPath", result.stdout)


if __name__ == "__main__":
    unittest.main()
