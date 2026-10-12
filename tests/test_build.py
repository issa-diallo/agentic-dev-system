"""BUILD validates actual Git assignments and current plans before dispatch."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

SOURCE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("agentic_build", SOURCE / "scripts/agentic-build.py")
BUILD = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BUILD)


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Test")
        (self.repo / "base").write_text("base\n")
        self.git("add", "base")
        self.git("commit", "-qm", "fixture")
        self.tree = self.root / "work"
        self.git("worktree", "add", "-q", "-b", "feat/a", str(self.tree))
        self.pr = self.unit("a", self.tree)
        self.plan = {"version": 1, "story": "story", "capabilities": ["a"], "prs": [self.pr]}
        self.manifest = self.root / "plan.json"

    def git(self, *args, repo=None):
        return subprocess.run(["git", "-C", str(repo or self.repo), *args],
                              check=True, capture_output=True).stdout.decode().strip()

    def unit(self, name, tree):
        return {"id": name, "reason": "Deliver " + name, "capabilities": [name],
                "files": [name + ".py"], "acceptance": ["Expected behavior"],
                "tests": ["Behavior tests"], "contracts": [], "depends_on": [],
                "branch": "feat/" + name, "worktree": str(tree), "implementer": "author"}

    def prepare(self, completed=()):
        self.manifest.write_text(json.dumps(self.plan))
        return BUILD.prepare(self.manifest, self.repo, "a", completed)

    def blocked(self, message):
        with self.assertRaisesRegex(BUILD.Blocked, message):
            self.prepare()

    def test_valid_contract_and_hash_change(self):
        first = self.prepare()
        self.assertEqual(first["worktree"], str(self.tree))
        self.assertEqual(first["files"], ["a.py"])
        self.pr["reason"] = "Deliver revised behavior"
        self.assertNotEqual(first["plan_sha256"], self.prepare()["plan_sha256"])
        self.pr["acceptance"] = []
        self.blocked("acceptance")

    def test_regrouped_capabilities_and_cycles_block(self):
        self.plan["capabilities"].append("b")
        self.pr["capabilities"].append("b")
        self.blocked("separable capabilities")
        self.pr["capabilities"] = ["a"]
        other = self.unit("b", self.root / "other")
        self.plan["prs"].append(other)
        self.pr["depends_on"] = ["b"]
        other["depends_on"] = ["a"]
        self.blocked("dependency cycle")

    def test_wrong_branch_main_and_unrelated_repository_block(self):
        self.pr["branch"] = "feat/wrong"
        self.blocked("wrong branch")
        self.pr.update(branch="main", worktree=str(self.repo))
        self.blocked("main/master")
        self.pr.update(branch="feat/a", worktree=str(self.root))
        self.blocked("Git check failed")

    def test_dirty_scope_preserves_local_changes(self):
        (self.tree / "a.py").write_text("allowed\n")
        self.prepare()
        (self.tree / "outside.py").write_text("preserve me\n")
        self.blocked("outside.py")
        self.assertEqual((self.tree / "outside.py").read_text(), "preserve me\n")

    def test_rename_source_outside_scope_blocks(self):
        self.git("mv", "base", "a.py", repo=self.tree)
        self.blocked("base")

    def test_unrelated_repository_blocks(self):
        foreign = self.root / "foreign"
        self.git("clone", "-q", str(self.repo), str(foreign))
        self.pr["worktree"] = str(foreign)
        self.blocked("not linked")

    def test_dependencies_require_explicit_completion(self):
        self.plan["capabilities"].append("b")
        self.plan["prs"].append(self.unit("b", self.root / "other"))
        self.pr["depends_on"] = ["b"]
        self.blocked("dependencies not completed")
        self.assertEqual(self.prepare(["b"])["dependencies"], ["b"])

    def test_cli_blocks_current_invalid_plan_despite_declared_pass(self):
        self.plan["verdict"] = "PASS"
        self.pr["acceptance"] = []
        self.manifest.write_text(json.dumps(self.plan))
        result = subprocess.run(["python3", str(SOURCE / "scripts/agentic-build.py"),
                                 str(self.manifest), "--repo", str(self.repo), "--pr", "a"],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["verdict"], "BLOCKED")


if __name__ == "__main__":
    unittest.main()
